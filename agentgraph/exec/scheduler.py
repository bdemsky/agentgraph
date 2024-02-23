import asyncio
import contextvars
import sys
import threading
import traceback
import time

from agentgraph.exec.engine import Engine
from agentgraph.core.graph import VarMap, GraphNested, GraphNode, GraphPythonAgent, GraphVarWait, createPythonAgent, createLLMAgent
from agentgraph.core.mutvar import MutVar
from agentgraph.core.var import Var
from agentgraph.core.varset import VarSet
from agentgraph.core.msgseq import MsgSeq
from agentgraph.core.tools import Tool
from agentgraph.core.llmmodel import LLMModel
import agentgraph.config

currentTask = contextvars.ContextVar('currentTask', default = None)
currentScheduler = contextvars.ContextVar('scheduler', default = None)

def getCurrentTask():
    return currentTask.get()

def setCurrentTask(task):
    currentTask.set(task)

def getCurrentScheduler():
    return currentScheduler.get()

def setCurrentScheduler(scheduler):
    currentScheduler.set(scheduler)

class ScheduleNode:
    """Schedule node to track dependences for a task instance."""
    
    def __init__(self, node: GraphNode):
        self.node = node
        self.waitMap = dict()
        self.inVarMap = dict()
        self.depCount = 0
        self.refs = set()
        
    def addRef(self, ref) -> bool:
        """Keeps track of the heap references this task will use.  If
        we see the same reference multiple times, return false for the
        duplicates"""
        
        if ref in self.refs:
            return False
        self.refs.add(ref)
        return True

    def getRefs(self) -> set:
        return self.refs
    
    def assertOwnership(self):
        for ref in self.refs:
            if isinstance(ref, agentgraph.core.mutable.Mutable):
                ref.setOwner(self)
                
    def setDepCount(self, depCount: int):
        """Sets Dependency count"""
        
        self.depCount = depCount

    def decDepCount(self) -> bool:
        """Decrement the outstanding dependence count.  If it hits
        zero, then we are ready to run."""
        
        count = self.depCount - 1
        self.depCount = count;
        return count == 0

    def getGraphNode(self) -> GraphNode:
        """Returns the underlying graph node this task will execute."""
        
        return self.node

    def addWaiter(self, var: Var, node):
        """Add a schedulenode that is waiting on us for value of the
        variable var."""
        
        if var in self.waitMap:
            list = self.waitMap[var]
        else:
            list = []
            self.waitMap[var] = list
        list.append(node)

    def getWaiters(self) -> dict:
        """Returns a map of waiters.  This maps maps our output
        variables to the set of schedule nodes that need that value
        from us."""
        
        return self.waitMap

    def setOutVarMap(self, outVarMap: dict):
        self.outVarMap = outVarMap

    def getOutVarMap(self):
        return self.outVarMap
    
    def getOutVarVal(self, var: Var):
        """Returns the output value for the variable var."""
        
        return self.outVarMap[var]

    def setInVarVal(self, var: Var, val):
        """Returns the input value for the variable var.  If we are
        still waiting on that value, then it will return the
        ScheduleNode that will provide the value."""

        self.inVarMap[var] = val

    def getInVarMap(self):
        """Returns the inVarMap mapping."""
        
        return self.inVarMap
        
    async def run(self):
        """Run the node"""
        self.outVarMap = await self.node.execute(self.getInVarMap())

    def threadRun(self, scheduler: 'Scheduler'):
        """Run the node"""
        self.outVarMap = self.node.execute(scheduler, self.getInVarMap())

dummyTask = ScheduleNode(None)
            
class ScoreBoardNode:
    """ScoreBoard linked list node to track heap dependences."""

    def __init__(self, isReader: bool):
        """Create a new scoreboard node.  The isRead parameter is
        True is this is a reader node and false if it is a writer
        node."""
        
        self.isReader = isReader
        self.waiters = set()
        self.next = None

    def getIsReader(self) -> bool:
        """Returns true if the node in question is for readers."""

        return self.isReader

    def setNext(self, next: 'ScoreBoardNode'):
        """Sets the next scoreboard node."""
        
        self.next = next

    def getNext(self) -> 'ScoreBoardNode':
        """Returns the next scoreboard node."""

        return self.next
        
    def addWaiter(self, waiter: ScheduleNode):
        """Adds a waiter to this scoreboard node."""
        
        self.waiters.add(waiter)

    def getWaiters(self) -> list:
        """Returns a list of waiting ScheduleNodes for this scoreboard
        node."""
        
        return self.waiters


class ScoreBoard:
    """ScoreBoard object to track object dependencies between agents."""
    
    def __init__(self):
        self.accesses = dict()
        
    def addReader(self, object, node: ScheduleNode) -> bool:
        """Add task node with read dependence on object.  Returns True
        if there is no conflict blocking execution."""

        if object in self.accesses:
            # We have a list of waiters.

            start, end = self.accesses[object]
        else:
            # If we are at the beginning, we can just return true and
            # do the snapshot.

            return True

        if not end.getIsReader():
            # We need to allocate a new node because the end is not a
            # reader node.
            
            scoreboardnode = ScoreBoardNode(True)
            scoreboardnode.addWaiter(node)
            end.setNext(scoreboardnode)
            end = scoreboardnode
            self.accesses[object] = (start, end)
        else:
            # We already have a reader node at the end, so just add
            # ourselves to it.
            
            end.addWaiter(node)
        return False
            
    def addWriter(self, object, node: ScheduleNode) -> bool:
        """Add task node with write dependence on object.  Returns
        True if there is no conflict blocking execution."""
        
        # Create a new scoreboard node for writing and add ourselves to
        # it.
        scoreboardnode = ScoreBoardNode(False)
        scoreboardnode.addWaiter(node)
        
        if object in self.accesses:
            # Already have a linked list, so add ourselves to it.
            start, end = self.accesses[object]
            end.setNext(scoreboardnode)
            self.accesses[object] = (start, scoreboardnode)
            return False
        else:
            # We are the first node.
            self.accesses[object] = (scoreboardnode, scoreboardnode)
            return True


    def removeWaiter(self, object, node: ScheduleNode, scheduler: 'Scheduler') -> bool:
        """Removes a waiting schedulenode from the list.  Returns
        false if that node had already cleared this queue and true if
        it was still waiting."""

        first, last = self.accesses[object]
        if node in first.getWaiters():
            first.getWaiters().remove(node)
            if len(first.getWaiters()) == 0:
                if first == last:
                    del self.accesses[object]
                else:
                    self.accesses[object] = (first.getNext(), last)
                    #Update scheduler
                    for nextnode in first.getNext().getWaiters():
                        scheduler.decDepCount(nextnode)
            return False
        else:
            entry = first.getNext()
            prev = first
            while entry != None:
                if node in entry.getWaiters():
                    entry.getWaiters().remove(node)
                    if len(entry.getWaiters()) == 0:
                        prev.setNext(entry.getNext())
                        #See if we eliminated tail and thus need to update queue
                        if last == entry:
                            self.accesses[object] = (first, prev)
                    break
                prev = entry
                entry = entry.getNext()
        return True

class TaskNode:
    def __init__(self, node: GraphNode, varMap: dict):
        self.node = node
        self.varMap = varMap
        self.next = None

    def setNext(self, next: 'TaskNode'):
        self.next = next

    def getNext(self):
        return self.next
        
    def getVarMap(self) -> dict:
        return self.varMap

    def getNode(self) -> GraphNode:
        return self.node

class Scheduler:
    """Scheduler class.  This does all of the scheduling for a given Nested Graph."""

    def __init__(self, model: LLMModel, scope: ScheduleNode, parent: 'Scheduler', engine: Engine):
        """
        Object initializer for a new Scheduler:
        model - the model we want to use by default

        scope - the scope we are scheduling

        parent - the Scheduler for our parent scope or None

        engine - the execution Engine we use
        """

        self.model = model
        self.scope = scope
        self.varMap = dict()
        self.parent = parent
        self.engine = engine
        self.scoreboard = ScoreBoard()
        self.windowSize = 0
        self.windowStall = None
        self.startTasks = None
        self.endTasks = None
        self.lock = threading.Lock()
        self.condVar = threading.Condition()
        self.dummyVar = MutVar("Dummy$$$$$")

    def getDefaultModel(self) -> LLMModel:
        return self.model
        
    def objAccess(self, mutable):
        """
        Waits for object access
        """
        gvar = GraphVarWait([self.dummyVar], self.condVar)
        varDict = dict()
        varDict[self.dummyVar] = mutable
        self.addTask(gvar, None, varDict)
        with self.condVar:
            while not gvar.isDone():
                self.condVar.wait()
        
    def readVariable(self, var: Var):
        """
        Reads value of variable, stalling if needed.
        """
        
        gvar = GraphVarWait([var], self.condVar)
        self.addTask(gvar, None, dict())
        #Wait for our task to finish
        with self.condVar:
            while not gvar.isDone():
                self.condVar.wait()
        return gvar[var]
                
    def addTask(self, node: GraphNode, vm: VarMap = None, varMap: dict = None):
        """
        Adds a new task for the scheduler to run.
        node - a GraphNode to run
        varMap - a map of Vars to values
        """

        if vm is not None:
            varMap = vm.getVarMap()
        if varMap is None:
            varMap = dict()
        taskNode = TaskNode(node, varMap)

        if self.endTasks == None:
            self.startTasks = taskNode
        else:
            self.endTasks.setNext(taskNode)

        self.endTasks = taskNode
        with self.lock:
            self._finishAddTask(varMap, node)

    def _finishAddTask(self, varMap: dict, node: GraphNode):
        self._checkForMutables(node, varMap)
        
        if (self.startTasks == self.endTasks):
            self._runTask(self.endTasks)
            
    def _checkVarForMutable(self, varMap: dict, writeSet: set, currSchedulerTask: ScheduleNode, v):
        """
        Check whether v is a mutable that we need to revoke ownership
        for.
        """
        if not isinstance(v, agentgraph.core.var.Var):
            value = v
        elif v in writeSet:
            # See if v is written by some prior task and thus by
            # assumption is not a mutable the parent has access
            # to.
            return
        elif v in varMap:
            value = varMap[v]
        elif v in self.varMap:
            value = self.varMap[v]
        else:
            return
        
        if isinstance(value, agentgraph.core.mutable.Mutable):
            mutTask = value.getOwner()
            # See if parent owns this Mutable.  If so, we know
            # there will be no race when we revoke ownership
            # by setting the owner to dummyTask.  If the
            # parent doesn't own the Mutable, it won't be
            # racing with children, and so we have no problem.
            if mutTask == currSchedulerTask:
                value.setOwner(dummyTask)
            
    def _checkForMutables(self, node: GraphNode, varMap: dict):
        """
        Handle and references to mutable objects.  If a mutable
        object is owned by the parent task, revoke ownership.
        """

        writeSet = set()
        currSchedulerTask = getCurrentTask()
        while node is not None:
            for var in node.getReadSet():
                if isinstance(var, VarSet):
                    for v in var:
                        self._checkVarForMutable(varMap, writeSet, currSchedulerTask, v)
                else:
                    self._checkVarForMutable(varMap, writeSet, currSchedulerTask, var)
                    
            writeSet.update(node.getWriteVars())
            node = node.getNext(0)


    def _runTask(self, task: TaskNode):
        """Starts up the first task."""

        # Update scheduler variable map with task variable map...
        for var in task.getVarMap():
            value = task.getVarMap()[var]
            self.varMap[var] = value

        self.scan(task.getNode())

    def runPythonAgent(self, pythonFunc, pos: list = None, kw: dict = None, outTypes: list = None, vmap: VarMap = None):
        if outTypes is None:
            out = None
        else:
            out = list()
            for type in outTypes:
                out.append(type.allocator())
        self.addTask(createPythonAgent(pythonFunc, pos, kw, out).start, vmap)
        if out is not None and len(out) == 1:
            return out[0]
        return out
        
    def runLLMAgent(self, msg: MsgSeq = None, conversation: Var = None, callVar: Var = None, tools: list[Tool] = None, formatFunc = None, pos: list = None, kw: dict = None, model: LLMModel = None, vmap: VarMap = None):
        outVar = Var()
        self.addTask(createLLMAgent(outVar, msg, conversation, callVar, tools, formatFunc, pos, kw, model).start, vmap)
        return outVar
        
    def checkFinishScope(self):
        if self.windowSize == 0:
            self.finishScope()

    def _scanNodeVar(self, node: GraphNode, scheduleNode: ScheduleNode, var, depCount: int) -> int:
        # Not a variable, so see if it is a Mutable
        if not isinstance(var, agentgraph.core.var.Var):
            if isinstance(var, agentgraph.core.mutable.Mutable):
                # Add ref and if we are new then add it as a writer and increment depCount...
                if scheduleNode.addRef(var):
                    if self.scoreboard.addWriter(var, scheduleNode) == False:
                        depCount += 1
            return depCount
                
        if var not in self.varMap:
            varName = var.getName()
            raise RuntimeError(f"Use before define with {varName}")
                    
        lookup = self.varMap[var]
        if isinstance(lookup, ScheduleNode):
            # Variable mapped to schedule node, which means we
            # haven't executed the relevant computation
            depCount += 1
            lookup.addWaiter(var, scheduleNode)
        else:
            # We have the value
            scheduleNode.setInVarVal(var, lookup)
            if var.isMutable():
                # If the variable is mutable, add ourselves.
                try:
                    depCount += self.handleReference(scheduleNode, var, lookup)
                except Exception as e:
                    print('Error', e)
                    print(traceback.format_exc())
                    return depCount
        return depCount
                    
    def scan(self, node: GraphNode):
        """Scans nodes in graph for scheduling purposes."""
        while True:
            if self.scope is not None and node == self.scope.getGraphNode():
                print("BAD")
                return
            depCount = 0
            inVars = node.getReadSet()
            outVars = node.getWriteVars()

            scheduleNode = ScheduleNode(node)

            # Compute our set of dependencies
            for var in inVars:
                if isinstance(var, VarSet):
                    for v in var:
                        depCount = self._scanNodeVar(node, scheduleNode, v, depCount)
                else:
                    depCount = self._scanNodeVar(node, scheduleNode, var, depCount)

            # Save our dependence count.
            scheduleNode.setDepCount(depCount)

            # Update variable map with any of our dependencies
            for var in outVars:
                self.varMap[var] = scheduleNode

            #Compute next node to scan
            self.windowSize += 1
            if (depCount == 0):
                self.startNestedTask(scheduleNode)
                
            node = node.getNext(0)
                
            if node == None:
                # Remove current task
                task = self.startTasks
                self.startTasks = task.getNext()
                if self.startTasks == None:
                    # No more work left so return
                    self.endTasks = None
                    return
                else:
                    # Start scheduling next task
                    nexttask = self.startTasks
                    node = nexttask.getNode()
                    for var in nexttask.getVarMap():
                        value = nexttask.getVarMap()[var]
                        self.varMap[var] = value   

    def handleReference(self, scheduleNode: ScheduleNode, var: Var, lookup) -> int:
        """We have a variable that references a mutable object.  So the
        variable has to be defined and we need to run it through the
        scoreboard to make sure all prior mutations are done.  This
        function returns the number of unresolved dependences due to
        this heap dependency."""
        if (scheduleNode.addRef(lookup) == False):
            return 0
        if var.isRead():
             if self.scoreboard.addReader(lookup, scheduleNode):
                 return 0
             else:
                 return 1
        if self.scoreboard.addWriter(lookup, scheduleNode):
            return 0
        else:
            return 1
        
    def completed(self, node: ScheduleNode):
        """
        Handles the completion of a task.  Forwards variable values
        to tasks that need those values.  Releases all of the heap
        dependences for the task.
        """
        self.windowSize -= 1
        
        if node == self.scope:
            #We just finished a python agent node
            self.checkFinishScope()
            return
        
        # Get list of tasks waiting on variables
        waiters = node.getWaiters()
        for var in waiters:
            # Get value  of output variable
            val = node.getOutVarVal(var)
            # Get list of waiters
            wlist = waiters[var]
            for n in wlist:
                #Forward value
                n.setInVarVal(var, val)
                if var.isMutable():
                    #If variable is mutable, register the heap dependence
                    if self.handleReference(n, var, val) == 0:
                        #Only do decrement if we didn't just transfer the count to a heap dependence
                        self.decDepCount(n)
                else:
                    #No heap dependence, so decrement count
                    self.decDepCount(n)

        outVarValMap = node.getOutVarMap()
        if outVarValMap is not None:
            for var in outVarValMap:
                # Pull ourselves out of any varMap entries and replace
                # with value so that future tasks are not waiting on us.
                if self.varMap[var] == node:
                    self.varMap[var] = outVarValMap[var]

        # Release our heap dependences
        refSet = node.getRefs()
        for r in refSet:
            self.scoreboard.removeWaiter(r, node, self)


        if self.windowSize < agentgraph.config.MAX_WINDOW_SIZE and self.windowStall != None:
            if self.windowStall != None:
                tmp = self.windowStall
                self.windowStall = None
                self.scan(tmp.getGraphNode())

        #Check if we need to finish scope off
        self.checkFinishScope()
        
    def decDepCount(self, node: ScheduleNode):
        """Decrement dependence count.  Starts task if dependence
        count gets to zero."""
        
        if node.decDepCount():
            #Ready to run this one now
            self.startTask(node)

    def finishScope(self):
        """Finish off a GraphNested node.  For now we require that all
        child tasks have completed before the nested completes.  More
        sophisticated implementations are possible that allow nodes to
        partially complete.

        """
        
        #See if anyone cares about the end of the scope
        if self.parent is None:
            return
        
        scheduleNode = self.scope
        graphnode = scheduleNode.getGraphNode()

        #Need to build value map to record the values the nested graph outputs
        if not isinstance(graphnode, GraphPythonAgent):
            writeMap = dict()
            writeSet = graphnode.getWriteVars()
            for var in writeSet:
                writeMap[var] = self.varMap[var]
            scheduleNode.setOutVarMap(writeMap)
        
        if self.parent is not None:
            with self.parent.lock:
                self.parent.completed(scheduleNode)
        else:
            print("This should not happen!")

            
    def startNestedTask(self, scheduleNode: ScheduleNode):
        """Starts task."""
        
        graphnode = scheduleNode.getGraphNode()

        scheduleNode.assertOwnership()
        
        if isinstance(graphnode, GraphNested):
            # Need start new Scheduler
            if isinstance(graphnode, GraphPythonAgent):
                # Start scheduler for PythonAgent child
                child = Scheduler(self.model, scheduleNode, self, self.engine)
                #Add a count for the PythonAgent task
                child.windowSize = 1
                self.engine.threadQueueItem(scheduleNode, child)
                return
            
            inVarMap = scheduleNode.getInVarMap()            
            child = Scheduler(self.model, scheduleNode, self, self.engine)
            child.addTask(graphnode.getStart(), None, varMap = inVarMap)
        else:
            #Schedule the job
            self.engine.queueItem(scheduleNode, self)

    def startTask(self, scheduleNode: ScheduleNode):
        """Starts task including conditional branch instruction."""
        
        graphnode = scheduleNode.getGraphNode()
        self.startNestedTask(scheduleNode)

    def shutdown(self):
        """Shutdown the engine.  Care should be taken to ensure engine
        is only shutdown once."""

        if (self.parent is not None):
            raise RuntimeError("Calling shutdown on non-parent Scheduler.")
        else:
            # Make sure there are no tasks in flight
            while self.windowSize != 0:
                time.sleep(0.001)
            # All good, shutdown the system
            self.engine.shutdown()
            self.getDefaultModel().print_statistics()
