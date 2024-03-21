import asyncio
import contextvars
import sys
import threading
import traceback
import time

from agentgraph.exec.engine import Engine, threadrun
from agentgraph.core.graph import VarMap, GraphNested, GraphNode, GraphPythonAgent, GraphVarWait, createPythonAgent, createLLMAgent
from agentgraph.core.var import Var
from agentgraph.core.vardict import VarDict
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
    
    def __init__(self, node: GraphNode, id: int):
        self.node = node
        self.waitMap = dict()
        self.inVarMap = dict()
        self.depCount = 0
        self.refs = set()
        self.id = id
        
    def addRef(self, ref) -> bool:
        """Keeps track of the heap references this task will use.  If
        we see the same reference multiple times, return false for the
        duplicates"""
        
        root = ref.getRootObject()
        if root in self.refs:
            return False
        self.refs.add(root)
        return True

    def getRefs(self) -> set:
        return self.refs
   
    def getId(self) -> int:
        return self.id

    def assertOwnership(self):
        for ref in self.refs:
            if isinstance(ref, agentgraph.core.mutable.Mutable):
                ref.setOwningTask(self)
                
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

dummyTask = ScheduleNode(None, 0)
            
class ScoreBoardNode:
    """ScoreBoard linked list node to track heap dependences."""

    def __init__(self, isReader: bool):
        """Create a new scoreboard node.  The isRead parameter is
        True is this is a reader node and false if it is a writer
        node."""
        
        self.isReader = isReader
        self.waiters = set()
        self.next = None
        self.pred = None
        self.idRange = None

    def clearPred(self):
        self.pred = None

    def getIdRange(self) -> tuple[int, int]:
        return self.idRange

    def getIsReader(self) -> bool:
        """Returns true if the node in question is for readers."""

        return self.isReader

    def setNext(self, next: 'ScoreBoardNode'):
        """Sets the next scoreboard node."""
        
        self.next = next
        next.pred = self

    def getPred(self) -> 'ScoreBoardNode':
        """Returns the previous scoreboard node."""

        return self.pred

    def getNext(self) -> 'ScoreBoardNode':
        """Returns the next scoreboard node."""

        return self.next
        
    def addWaiter(self, waiter: ScheduleNode):
        """Adds a waiter to this scoreboard node."""

        if self.idRange is None:
            self.idRange = waiter.id, waiter.id
        else:
            self.idRange = min(self.idRange[0], waiter.id), max(self.idRange[1], waiter.id)
        self.waiters.add(waiter)

    def getWaiters(self) -> list:
        """Returns a list of waiting ScheduleNodes for this scoreboard
        node."""
        
        return self.waiters

    @staticmethod
    def split_node(reader: 'ScoreBoardNode', writer: 'ScoreBoardNode') -> tuple['ScoreBoardNode', 'ScoreBoardNode']:
        # writer node should have a single id for id range
        writer_id = writer.idRange[0]
        before_write, after_write = ScoreBoardNode(True), ScoreBoardNode(True)
        for waiter in reader.waiters:
            if waiter.getId() < writer_id:
                before_write.addWaiter(waiter)
            elif waiter.getId() > writer_id:
                after_write.addWaiter(waiter)

        before_write.setNext(writer)
        writer.setNext(after_write)
        return before_write, after_write


    @staticmethod
    def merge(this: 'ScoreBoardNode', that: 'ScoreBoardNode') -> tuple['ScoreBoardNode', 'ScoreBoardNode']:
        """merge two nodes with overlapping id ranges. """

        if this.idRange[1] < that.idRange[0] or that.idRange[1] < this.idRange[0]:
            print("BAD")
            return

        if this.isReader and that.isReader:
            reader = ScoreBoardNode(True)
            reader.waiters = this.waiters | other.waiters
            reader.idRange = min(this.idRange[0], that.idRange[0]), max(this.idRange[1], that.idRange[1])
            return reader, reader

        writer = ScoreBoardNode(False)
        if this.isReader:
            reader = this
            writer.waiters = that.waiters
            writer.idRange = that.idRange
        else:
            writer.waiters = this.waiters
            writer.idRange = this.idRange
            if that.isReader:
                reader = that
            else:
                return writer, writer

        return split_node(reader, writer)

class ScoreBoard:
    """ScoreBoard object to track object dependencies between agents."""
    
    def __init__(self):
        self.accesses = dict()

    def addReader(self, object, node: ScheduleNode) -> bool:
        """Add task node with read dependence on object.  Returns True
        if there is no conflict blocking execution."""

        root = object.getRootObject()
        if root in self.accesses:
            # We have a list of waiters.

            start, end = self.accesses[root]
        else:
            # If we are at the beginning, we can just return true and
            # do the snapshot.

            return True

        id = node.getId()
        curr = end

        while curr is not None:
            pred = curr.getPred()
            if not curr.getIsReader():
                # Write node...  We should add after as long as our id
                # is larger.
                if curr.getIdRange()[1] < id:
                    scoreboardnode = ScoreBoardNode(True)
                    scoreboardnode.addWaiter(node)
                    oldNext = curr.getNext()
                    curr.setNext(scoreboardnode)
                    if curr == end:
                        self.accesses[root] = (start, scoreboardnode)
                    else:
                        scoreboardnode.setNext(oldNext)

                    return False
            else:
                # Read node, can add as long as we should not be ahead
                # of its predecessor
                if pred == None or pred.getIdRange()[1] < id:
                    curr.addWaiter(node)
                    return False
            curr = pred

        # Made it to the front of the list.
        #
        # BD: I don't think this case is actually possible since the
        # only case where we are not added at the end is if there is a
        # variable resolution.  But then we should be after the
        # variable assignment task, and it has not released its heap
        # references yet.
        #

        raise RuntimeException("Impossible Case")

            
    def addWriter(self, object, node: ScheduleNode) -> bool:
        """Add task node with write dependence on object.  Returns
        True if there is no conflict blocking execution."""
        
        # Create a new scoreboard node for writing and add ourselves to
        # it.
        scoreboardnode = ScoreBoardNode(False)
        scoreboardnode.addWaiter(node)
        
        root = object.getRootObject()
        if root in self.accesses:
            # Already have a linked list, so add ourselves to it.
            start, end = self.accesses[root]
        else:
            # We are the first node.
            self.accesses[root] = (scoreboardnode, scoreboardnode)
            return True

        id = node.getId()
        curr = end

        while curr is not None:
            range = curr.getIdRange()
            if id > range[1]:
                oldNext = curr.getNext()
                curr.setNext(scoreboardnode)
                if curr == end:
                    self.accesses[root] = (start, scoreboardnode)
                else:
                    scoreboardnode.setNext(oldNext)
                return False
            elif id > range[0]:
                # We have a write splitting a read node...
                first, last = ScoreBoardNode.split_node(curr, scoreboardnode)
                pred = curr.getPred()
                succ = curr.getNext()
                if pred is None:
                    # This case shouldn't be possible, because the
                    # only case where we traverse is for returning a
                    # mutable references, and a reader shouldn't be
                    # able to provide a reference to some later
                    # writer...
                    raise RuntimeException("Predecessor should never be None")

                pred.setNext(first)

                if succ is None:
                    self.accesses[root] = (start, last)
                    return False
                else:
                    last.setNext(succ)
                return False

            curr = curr.getPred()

        # BD: I don't think this case is actually possible since the
        # only case where we are not added at the end is if there is a
        # variable resolution.  But then we should be after the
        # variable assignment task, and it has not released its heap
        # references yet.
        raise RuntimeException("Impossible case")


    def removeWaiter(self, object, node: ScheduleNode, scheduler: 'Scheduler') -> bool:
        """Removes a waiting schedulenode from the list.  Returns
        false if that node had already cleared this queue and true if
        it was still waiting."""
        root = object.getRootObject()
        first, last = self.accesses[root]
        if node in first.getWaiters():
            first.getWaiters().remove(node)
            if len(first.getWaiters()) == 0:
                if first == last:
                    del self.accesses[root]
                else:
                    newfirst = first.getNext()
                    newfirst.clearPred()
                    self.accesses[root] = (newfirst, last)
                    #Update scheduler
                    for nextnode in newfirst.getWaiters():
                        scheduler.decDepCount(nextnode)
            return False
        else:
            # BCD: Can this branch ever be called??
            entry = first.getNext()
            prev = first
            while entry != None:
                if node in entry.getWaiters():
                    entry.getWaiters().remove(node)
                    if len(entry.getWaiters()) == 0:
                        entry.clearPred()
                        prev.setNext(entry.getNext())
                        #See if we eliminated tail and thus need to update queue
                        if last == entry:
                            self.accesses[root] = (first, prev)
                    break
                prev = entry
                entry = entry.getNext()
            return True

    def mergeAccessQueues(self, source, dest):
        """
        merge the accesse queue of source to that of dest according to schedule node ids
        """

        if source not in self.accesses:
            return

        if dest not in self.accesses:
            self.accesses[dest] = self.accesses[source]
            del self.accesses[source]
            return  

        srcNode, srcLast = self.accesses[source]
        dstNode, dstLast = self.accesses[dest]

        if srcNode.getIdRange()[1] < dstNode.getIdRange()[0]:
            first = curNode = srcNode
            srcNode = srcNode.getNext()
        elif dstNode.getIdRange()[1] < srcNode.getIdRange()[0]:
            first = curNode = dstNode
            dstNode = dstNode.getNext()
        else:
            first, curNode = ScoreBoardNode.merge(srcNode, dstNode)
            srcNode = srcNode.getNext()
            dstNode = dstNode.getNext()

        while srcNode != None and dstNode != None:
            if srcNode.getIdRange()[1] < dstNode.getIdRange()[0]:
                curNode.setNext(srcNode)
                curNode = srcNode
                srcNode = srcNode.getNext()
            elif dstNode.getIdRange()[1] < srcNode.getIdRange()[0]:
                curNode.setNext(dstNode)
                curNode = dstNode
                dstNode = dstNode.getNext()
            else:
                start, end = ScoreBoardNode.merge(srcNode, dstNode)
                curNode.setNext(start)
                curNode = end
                srcNode = srcNode.getNext()
                dstNode = dstNode.getNext()
        
        if srcNode != None:
            curNode.setNext(srcNode)
            last = srcLast
        elif dstNode != None:
            curNode.setNext(dstNode)
            last = dstLast
        else:
            last = curNode

        self.accesses[dest] = first, last
        del self.accesses[source]

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
        self.dummyVar = Var("Dummy$$$$$")
        self.nextId = 1
        self.children = set()
        self.childrenLock = threading.Lock()

    def _getNewId(self) -> int:
        id = self.nextId
        self.nextId += 1
        return id

    def getDefaultModel(self) -> LLMModel:
        return self.model
        
    def mergeObjAccesses(self, source, dest):
        """
        merge accesses from object source in current and all parent schedulers
        """
        scheduler = self
        while scheduler != None:
            with scheduler.lock:
                scheduler.scoreboard.mergeAccessQueues(source, dest)
            scheduler = scheduler.parent
        
    def objAccess(self, mutable):
        """
        Waits for object access
        """
        gvar = GraphVarWait([self.dummyVar], self.condVar)
        varDict = dict()
        varDict[self.dummyVar] = mutable.getRootObject()
        self.addTask(gvar, None, varDict)
        self.waitOnGvar(gvar)
        
    def readVariable(self, var: Var):
        """
        Reads value of variable, stalling if needed.
        """
        
        gvar = GraphVarWait([var], self.condVar)
        self.addTask(gvar)
        #Wait for our task to finish
        self.waitOnGvar(gvar)
        return gvar[var]
    
    def waitOnGvar(self, gvar):
        """
        Wait for condVar or steal a child task on timeout.
        """
        with self.condVar:
            while not gvar.isDone():
                if not self.condVar.wait(timeout=0.1):
                    self.condVar.release()
                    try:
                        self.stealChildTask()
                    finally:
                        self.condVar.acquire()

    def stealChildTask(self):
        child = self.getPendingChild()
        if child:
            threadrun(self.engine, child.scope, child)
            setCurrentScheduler(self)
    
    def getPendingChild(self):
        """
        Find a child task that has not started running.
        """
        with self.childrenLock:
            for child in self.children:
                if child.future.cancel():
                    return child
                descendent = child.getPendingChild()
                if descendent != None:
                    return descendent


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
            mutTask = value.getOwningTask()
            # See if parent owns this Mutable.  If so, we know
            # there will be no race when we revoke ownership
            # by setting the owner to dummyTask.  If the
            # parent doesn't own the Mutable, it won't be
            # racing with children, and so we have no problem.
            if mutTask == currSchedulerTask:
                value.setOwningTask(dummyTask)
            
    def _checkForMutables(self, node: GraphNode, varMap: dict):
        """
        Handle and references to mutable objects.  If a mutable
        object is owned by the parent task, revoke ownership.
        """

        writeSet = set()
        currSchedulerTask = getCurrentTask()
        while node is not None:
            for var in node.getReadSet():
                if isinstance(var, VarDict):
                    for v in var.values():
                        self._checkVarForMutable(varMap, writeSet, currSchedulerTask, v)
                elif isinstance(var, VarSet):
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

    def runPythonAgent(self, pythonFunc, pos: list = None, kw: dict = None, numOuts: int = 0, vmap: VarMap = None):
        out = None
        if numOuts > 0:
            out = list()
            for v in range(numOuts):
                out.append(agentgraph.Var())
        self.addTask(createPythonAgent(pythonFunc, pos, kw, out).start, vmap)
        if numOuts == 1:
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
            if isinstance(lookup, agentgraph.core.mutable.Mutable):
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

            scheduleNode = ScheduleNode(node, self._getNewId())

            # Compute our set of dependencies
            for var in inVars:
                if isinstance(var, VarDict):
                    for v in var.values():
                        depCount = self._scanNodeVar(node, scheduleNode, v, depCount)
                elif isinstance(var, VarSet):
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
                if isinstance(val, agentgraph.core.mutable.Mutable):
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
            with self.parent.childrenLock:
                self.parent.children.remove(self)
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
                with self.childrenLock:
                    self.children.add(child)
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
            if agentgraph.config.VERBOSE > 0:
                self.getDefaultModel().print_statistics()
