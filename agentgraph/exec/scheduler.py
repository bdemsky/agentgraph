import asyncio
import sys
import threading
import traceback

from agentgraph.exec.engine import Engine
from agentgraph.core.graph import VarMap, GraphCall, GraphNested, GraphNode, GraphNodeBranch, GraphPythonAgent, GraphVarWait
from agentgraph.core.var import Var
import agentgraph.config

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
        we see the same reference multiple times, return false on the
        duplicates"""
        
        if ref in self.refs:
            return False
        self.refs.add(ref)
        return True
        
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

    def addWaiter(self, var: Var, node: 'ScheduleNode'):
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
    
    def getOutVarVal(self, var: Var):
        """Returns the output value for the variable var."""
        
        self.outVarMap[var]

    def setInVarVal(self, var: Var, val):
        """Returns the input value for the variable var.  If we are
        still waiting on that value, then it will return the
        ScheduleNode that will provide the value."""

        self.inVarMap[var] = val

    def getInVarMap(self):
        """Returns the inVarMap mapping."""
        
        return self.inVarMap
        
    async def run(self, scheduler: 'Scheduler'):
        """Run the node"""
        if isinstance(self.node, GraphPythonAgent):
            self.outVarMap = await self.node.execute(scheduler, self.getInVarMap())
        else:
            self.outVarMap = await self.node.execute(self.getInVarMap())
        
class ScoreBoardNode:
    """ScoreBoard linked list node to track heap dependences."""

    def __init__(self, isReader: bool):
        """Create a new scoreboard node.  The isRead parameter is
        True is this is a reader node and false if it is a writer
        node."""
        
        self.isReader = isReader
        self.waiters = set()
        self.next = None

    def isReader(self) -> bool:
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

        if not end.isReader():
            # We need to allocate a new node because the end is not a
            # reader node.
            
            scoreboardnode = ScoreBoardNode(true)
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
                    self.accesses[object] = None
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
    
    def __init__(self, scope: GraphNested, parent: 'Scheduler', engine: Engine):

        """Object initializer for a new Scheduler:
        scope - the scope we are scheduling

        parent - the Scheduler for our parent scope or None

        engine - the execution Engine we use
        """

        self.scope = scope
        self.varMap = dict()
        self.parent = parent
        self.engine = engine
        self.count = 0
        self.scoreboard = ScoreBoard()
        self.windowSize = 0
        self.windowStall = None
        self.startTasks = None
        self.endTasks = None
        self.condVar = threading.Condition()

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
                
    def addTask(self, node: GraphNode, vm: VarMap, varMap: dict = None):
        """
        Adds a new task for the scheduler to run.
        node - a GraphNode to run
        varMap - a map of Vars to values
        """

        if vm != None:
            varMap = vm.getVarMap()
        taskNode = TaskNode(node, varMap)

        if self.endTasks == None:
            self.startTasks = taskNode
        else:
            self.endTasks.setNext(taskNode)

        self.endTasks = taskNode
            
        if (self.startTasks == taskNode):
            self.runTask(taskNode, self.scope == None)
            
    def runTask(self, task: TaskNode, fromThread: bool):
        """Starts up the first task."""
        for var in task.getVarMap():
            value = task.getVarMap()[var]
            self.varMap[var] = value
            
        if fromThread:
            self.scan(task.getNode())
        else:
            self.engine.runScan(task.getNode(), self)
            
        
    def scan(self, node: GraphNode):
        """Scans nodes in graph for scheduling purposes."""
        while True:
            depCount = 0
            inVars = node.getReadVars()
            outVars = node.getWriteVars()
            scheduleNode = ScheduleNode(node)
            # Compute our set of dependencies
            for var in inVars:
                lookup = self.varMap[var]
                if isinstance(lookup, ScheduleNode):
                    # Variable mapped to schedule node, which means we haven't executed the relevant computation
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
                            return
                        
            # Save our dependence count.
            scheduleNode.setDepCount(depCount)
            
            # Update variable map with any of our dependencies
            for var in outVars:
                self.varMap[var] = scheduleNode
            if node == self.scope:
                return

            #Compute next node to scan
            if isinstance(node, GraphNodeBranch):
                # If we have a branchnode, we have to see if we know
                # the direction.
                if scheduleNode.depCount != 0:
                    return

                # Don't want dataflow graph construction to get too
                # far ahead of execution.
                if self.windowSize >= agentgraph.config.MAX_WINDOW_SIZE:
                    self.windowStall = scheduleNode
                    return
                edge = 1 if scheduleNode.inVarMap[node.getBranchVar()] else 0
                node = node.getNext(edge)
            else:
                self.windowSize += 1
                if (depCount == 0):
                    self.startBaseTask(scheduleNode, node)
                
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
                    nexttask = selt.startTasks
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
        """We call this when a task has completed."""

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
                    if handleReference(n, var, val) == 0:
                        #Only do decrement if we didn't just transfer the count to a heap dependence
                        decDepCount(n)
                else:
                    #No heap dependence, so decrement count
                    decDepCount(n)
        #Release our heap dependences
        inVarValMap = node.getInVarMap()
        for var in inVarValMap:
            if var.isMutable():
                val = inVarValMap[var]
                self.scoreboard.removeWaiter(val, node, self)
        self.windowSize -= 1
        if self.windowSize < agentgraph.config.MAX_WINDOW_SIZE and self.windowStall != None:
            if self.windowStall != None:
                tmp = self.windowStall
                self.windowStall = None
                self.scan(tmp.getGraphNode())
        

                
    def decDepCount(self, node: ScheduleNode):
        """Decrement dependence count.  Starts task if dependence
        count gets to zero."""
        
        if node.decDepCount():
            #Ready to run this one now
            self.startTask(node)
                    
    def startBaseTask(self, scheduleNode: ScheduleNode, graphnode: GraphNode):
        """Starts task."""
        
        graphnode = scheduleNode.getGraphNode()
        
        if graphnode == self.scope:
            #Dependences are resolve for final node
            self.windowSize -= 1
            #Need to build value map to record the values the nested graph outputs
            writeMap = dict()
            if isinstance(graphnode, GraphCall) and graphnode.outMap != None:
                writeSet = graphnode.call.getWriteVars()
                for var in writeSet:
                    if var in graphnode.call.outMap:
                        writeMap[graphnode.call.outMap[var]] = self.varMap[var]
                    else:
                        writeMap[var] = self.varMap[var]
            else:
                writeSet = graphnode.getWriteVars()
                for var in writeSet:
                    writeMap[var] = self.varMap[var]
            scheduleNode.setOutVarMap(writeMap)
                    
            if self.parent != None:
                self.parent.completed(scheduleNode)
            else:
                print("This should not happen!")
        elif isinstance(graphnode, GraphNested):
            # Need start new Scheduler
            if isinstance(graphnode, GraphPythonAgent):
                # Start scheduler for PythonAgent child
                child = Scheduler(graphnode, self, self.engine)
                self.engine.queueItem(scheduleNode, child)
                return
            
            inVarMap = scheduleNode.getInVarMap()            
            # If we are calling another graph, then need to do some
            # variable remapping
            if isinstance(graphnode, GraphCall) and graphnode.inMap != None:
                oldVarMap = inVarMap
                inVarMap = dict()
                readVars = graphnode.call.getReadVars();
                for v in readVars:
                    calleevar = v
                    if v in graphnode.inMap:
                        calleevar = graphnode.inMap[v]
                    inVarMap[v] = oldVarMap[calleevar]

            child = Scheduler(graphnode, self, self.engine)
            child.addTask(graphnode.getStart(), None, varMap = inVarMap)
        else:
            #Schedule the job
            self.engine.queueItem(scheduleNode, self)

    def startTask(self, scheduleNode: ScheduleNode):
        """Starts task including conditional branch instruction."""
        
        graphnode = scheduleNode.getGraphNode()
        
        if isinstance(graphnode, GraphNodeBranch):
            #Process branch task
            edge = 1 if scheduleNode.inVarMap[graphnode.getBranchVar()] else 0
            graphnode = graphnode.getNext(edge)
            self.scan(graphnode)
        else:
            self.startBaseTask(scheduleNode, graphnode)

    def shutdown(self):
        """Shutdown the engine.  Care should be taken to ensure engine
        is only shutdown once."""

        if (self.parent is not None):
            raise RuntimeException("Calling shutdown on non-parent Scheduler.")
        else:
            self.engine.shutdown()
