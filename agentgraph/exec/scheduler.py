import asyncio
import contextvars
import sys
import threading
import traceback
import time
from typing import Any, Dict, List, Optional, Set, Union

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
        self.waitMap: Dict[Var, list]  = dict()
        self.inVarMap: Dict[Var, Any] = dict()
        self.depCount = 0
        self.refs: Set['agentgraph.core.mutable.Mutable'] = set()
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

    def addWaiter(self, var: Var, node, reader: bool):
        """Add a schedulenode that is waiting on us for value of the
        variable var and whether it is a reader."""
        
        if var in self.waitMap:
            list = self.waitMap[var]
        else:
            list = []
            self.waitMap[var] = list
        list.append((node, reader))

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
        assert isinstance(self.node, agentgraph.core.graph.GraphPythonAgent)
        self.outVarMap = self.node.execute(scheduler, self.getInVarMap())

dummyTask = ScheduleNode(GraphNode(), 0)
            
class ScoreBoardNode:
    """ScoreBoard linked list node to track heap dependences."""

    def __init__(self, isReader: bool):
        """Create a new scoreboard node.  The isRead parameter is
        True is this is a reader node and false if it is a writer
        node."""
        
        self.isReader = isReader
        self.waiters: Set[ScheduleNode] = set()
        self.next: Optional['ScoreBoardNode'] = None
        self.pred: Optional['ScoreBoardNode'] = None
        self.idRange: Optional[tuple[int, int]] = None

    def clearPred(self):
        self.pred = None

    def getIdRange(self) -> tuple[int, int]:
        range = self.idRange
        assert range is not None
        return range

    def getIsReader(self) -> bool:
        """Returns true if the node in question is for readers."""

        return self.isReader

    def setNext(self, next: 'ScoreBoardNode'):
        """Sets the next scoreboard node."""
        
        self.next = next
        next.pred = self

    def getPred(self) -> Optional['ScoreBoardNode']:
        """Returns the previous scoreboard node."""

        return self.pred

    def getNext(self) -> Optional['ScoreBoardNode']:
        """Returns the next scoreboard node."""

        return self.next
        
    def addWaiter(self, waiter: ScheduleNode):
        """Adds a waiter to this scoreboard node."""

        range = self.idRange
        if range is None:
            self.idRange = waiter.id, waiter.id
        else:
            self.idRange = min(range[0], waiter.id), max(range[1], waiter.id)
        self.waiters.add(waiter)

    def getWaiters(self) -> Set[ScheduleNode]:
        """Returns a list of waiting ScheduleNodes for this scoreboard
        node."""
        
        return self.waiters

    @staticmethod
    def split_node(reader: 'ScoreBoardNode', writer: 'ScoreBoardNode') -> tuple['ScoreBoardNode', 'ScoreBoardNode']:
        # writer node should have a single id for id range
        writer_id = writer.getIdRange()[0]
        before_write, after_write = ScoreBoardNode(True), ScoreBoardNode(True)
        for waiter in reader.waiters:
            if waiter.getId() < writer_id:
                before_write.addWaiter(waiter)
            elif waiter.getId() > writer_id:
                after_write.addWaiter(waiter)

        # in case the writer is at the start or end of the reader
        # id range and the before/after node is empty
        if before_write.idRange != None:
            before_write.setNext(writer)
        else:
            before_write = writer
        
        if after_write.idRange != None:
            writer.setNext(after_write)
        else:
            after_write = writer

        return before_write, after_write


    @staticmethod
    def merge(this: 'ScoreBoardNode', that: 'ScoreBoardNode') -> tuple['ScoreBoardNode', 'ScoreBoardNode']:
        """merge two nodes with overlapping id ranges. """

        thisRange = this.getIdRange()
        thatRange = that.getIdRange()
        assert thisRange[1] >= thatRange[0] and thatRange[1] >= thisRange[0]

        if this.isReader and that.isReader:
            reader = ScoreBoardNode(True)
            reader.waiters = this.waiters | that.waiters
            reader.idRange = min(thisRange[0], thatRange[0]), max(thisRange[1], thatRange[1])
            return reader, reader

        writer = ScoreBoardNode(False)
        if this.isReader:
            reader = this
            writer.waiters = that.waiters
            writer.idRange = thatRange
        else:
            writer.waiters = this.waiters
            writer.idRange = thisRange
            if that.isReader:
                reader = that
            else:
                return writer, writer

        return ScoreBoardNode.split_node(reader, writer)

class ScoreBoard:
    """ScoreBoard object to track object dependencies between agents."""
    
    def __init__(self):
        self.accesses = dict()

    def addReader(self, object, node: ScheduleNode) -> bool:
        """Add task node with read dependence on object.  Returns True
        if there is no conflict blocking execution."""
        scoreboardnode = ScoreBoardNode(True)
        scoreboardnode.addWaiter(node)

        root = object.getRootObject()
        if root in self.accesses:
            # We have a list of waiters.

            start, end = self.accesses[root]
        else:
            # If we are at the beginning, we can just return true and
            # do the snapshot.
            self.accesses[root] = (scoreboardnode, scoreboardnode)
            return True

        id = node.getId()
        curr = end

        while curr is not None:
            pred = curr.getPred()
            if not curr.getIsReader():
                # Write node...  We should add after as long as our id
                # is larger.
                if curr.getIdRange()[1] < id:
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
                if pred is None or pred.getIdRange()[1] < id:
                    curr.addWaiter(node)
                    return curr == start
            curr = pred

        # Made it to the front of the list.
        #
        # BD: I don't think this case is actually possible since the
        # only case where we are not added at the end is if there is a
        # variable resolution.  But then we should be after the
        # variable assignment task, and it has not released its heap
        # references yet.
        #

        raise RuntimeError("Impossible Case")

            
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
                    raise RuntimeError("Predecessor should never be None")

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
        raise RuntimeError("Impossible case")


    def changeToWriter(self, object, node: ScheduleNode):
        """Change existing node from reader to writer. Returns
        True if there is no conflict blocking execution or if
        no change was made."""
        root = object.getRootObject()
        # Reference should already been previously added
        start, end = self.accesses[root]

        id = node.getId()
        curr = end

        while curr is not None:
            range = curr.getIdRange()
            if id > range[1]:
                raise RuntimeError("Impossible case")
            elif id >= range[0]:
                assert node in curr.getWaiters()
                if not curr.getIsReader():
                    # Node was already a writer
                    return True
                if len(curr.getWaiters()) == 1:
                    # Schedule node is the only one, just change node to writer
                    curr.isReader = False
                    return True
                
                # Split the node
                scoreboardnode = ScoreBoardNode(False)
                scoreboardnode.addWaiter(node)
                first, last = ScoreBoardNode.split_node(curr, scoreboardnode)
                pred = curr.getPred()
                succ = curr.getNext()
                if pred is None:
                    self.accesses[root] = (first, end)
                else:
                    pred.setNext(first)

                if succ is None:
                    self.accesses[root] = (first if pred is None else start, last)
                else:
                    last.setNext(succ)
                # Return false if it now has to wait since it is no longer a reader
                # unless it previously was already waiting
                return start != curr or first != scoreboardnode

            curr = curr.getPred()

        raise RuntimeError("Impossible case")


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
            while entry is not None:
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

        while srcNode is not None and dstNode is not None:
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
        
        if srcNode is not None:
            curNode.setNext(srcNode)
            last = srcLast
        elif dstNode is not None:
            curNode.setNext(dstNode)
            last = dstLast
        else:
            last = curNode

        self.accesses[dest] = first, last
        del self.accesses[source]

class TaskNode:
    def __init__(self, node: GraphNode, varMap: Dict[Var, Any]):
        self.node = node
        self.varMap = varMap
        self.next: Optional['TaskNode'] = None

    def setNext(self, next: 'TaskNode'):
        self.next = next

    def getNext(self) -> Optional['TaskNode']:
        return self.next
        
    def getVarMap(self) -> dict:
        return self.varMap

    def getNode(self) -> GraphNode:
        return self.node

class Scheduler:
    """Scheduler class.  This does all of the scheduling for a given Nested Graph."""

    def __init__(self, model: LLMModel, scope: Optional[ScheduleNode], parent: Optional['Scheduler'], engine: Engine):
        """
        Object initializer for a new Scheduler:
        model - the model we want to use by default

        scope - the scope we are scheduling

        parent - the Scheduler for our parent scope or None

        engine - the execution Engine we use
        """

        self.model = model
        self.scope = scope
        self.varMap: Dict[Var, Any] = dict()
        self.parent = parent
        self.engine = engine
        self.scoreboard = ScoreBoard()
        self.windowSize = 0
        self.windowStall = None
        self.startTasks: Optional[TaskNode] = None
        self.endTasks: Optional[TaskNode] = None
        self.lock = threading.Lock()
        self.condVar = threading.Condition()
        self.sleepVar = threading.Condition()
        self.dummyVar = Var("Dummy$$$$$")
        self.nextId = 1
        self.children: Set['Scheduler'] = set()
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
        while scheduler is not None:
            with scheduler.lock:
                scheduler.scoreboard.mergeAccessQueues(source, dest)
            scheduler = scheduler.parent
        
    def objAccess(self, mutable, readonly=False):
        """
        Waits for object access
        """
        gvar = GraphVarWait([self.dummyVar], self.condVar)
        varDict = dict()
        if readonly:
            varDict[self.dummyVar] = agentgraph.core.mutable.ReadOnly(mutable.getRootObject())
        else:
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
                if self.engine.getPendingPythonTaskCount() > 0:
                    self.condVar.release()
                    taskStolen = False
                    try:
                        taskStolen = self.stealChildTask()
                    finally:
                        self.condVar.acquire()
                        # Make sure we didn't miss the event while we
                        # tried to steal task.
                        if gvar.isDone():
                            return
                        # If we stole a task successfully, loop again
                        # without waiting
                        if taskStolen:
                            continue
                # Did not successfully steal task, so wait and give up lock
                self.condVar.wait(timeout=0.01)

    def stealChildTask(self) -> bool:
        child = self.getPendingChild()
        if child:
            threadrun(self.engine, child.scope, child)
            setCurrentScheduler(self)
            return True
        else:
            return False

    def getPendingChild(self):
        """
        Find a child task that has not started running.
        """
        with self.childrenLock:
            for child in self.children:
                if child.future.cancel():
                    return child
                descendent = child.getPendingChild()
                if descendent is not None:
                    return descendent


    def addTask(self, node: GraphNode, vm: Optional[VarMap] = None, varMap: Optional[dict] = None):
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

        if self.endTasks is None:
            self.startTasks = taskNode
        else:
            self.endTasks.setNext(taskNode)

        self.endTasks = taskNode
        with self.lock:
            self._finishAddTask(varMap, node)

    def _finishAddTask(self, varMap: dict, node: GraphNode):
        self._checkForMutables(node, varMap)
        
        if (self.startTasks == self.endTasks):
            runTask = self.endTasks
            assert runTask is not None
            self._runTask(runTask)
            
    def _checkVarForMutable(self, varMap: dict, writeSet: Set[Var], currSchedulerTask: ScheduleNode, v):
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
            
    def _checkForMutables(self, node: Optional[GraphNode], varMap: dict):
        """
        Handle and references to mutable objects.  If a mutable
        object is owned by the parent task, revoke ownership.
        """

        writeSet: Set[Var] = set()
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

    def runPythonAgent(self, pythonFunc, pos: Optional[list] = None, kw: Optional[dict] = None, numOuts: int = 0, vmap: Optional[VarMap] = None):
        out = None
        if numOuts > 0:
            out = list()
            for v in range(numOuts):
                out.append(agentgraph.Var())
        self.addTask(createPythonAgent(pythonFunc, pos, kw, out).start, vmap)
        if numOuts == 1:
            return out[0]
        return out
        
    def runLLMAgent(self, msg: Optional[MsgSeq] = None, conversation: Union[Var, None, 'agentgraph.core.conversation.Conversation'] = None, callVar: Optional[Var] = None, tools: Optional['agentgraph.core.tools.ToolList'] = None, formatFunc = None, pos: Optional[list] = None, kw: Optional[dict] = None, model: Optional[LLMModel] = None, vmap: Optional[VarMap] = None):
        outVar = Var()
        self.addTask(createLLMAgent(outVar, msg, conversation, callVar, tools, formatFunc, pos, kw, model).start, vmap)
        return outVar
        
    def checkFinishScope(self):
        if self.windowSize == 0:
            self.finishScope()

    def _scanNodeVar(self, node: GraphNode, scheduleNode: ScheduleNode, var, depCount: int) -> int:
        if isinstance(var, agentgraph.core.mutable.ReadOnly):
            var = var.getMutable()
            reader = True
        elif isinstance(var, agentgraph.core.mutable.ReadOnlyProxy):
            var = var._mutable
            reader = True
        else:
            reader = False
        # Not a variable, so see if it is a Mutable
        if not isinstance(var, agentgraph.core.var.Var):
            if isinstance(var, agentgraph.core.mutable.Mutable):
                # Add ref and if we are new then add it as a writer and increment depCount...
                if scheduleNode.addRef(var):
                    if reader:
                        if self.scoreboard.addReader(var, scheduleNode) == False:
                            depCount += 1
                    else:
                        if self.scoreboard.addWriter(var, scheduleNode) == False:
                            depCount += 1
                else:
                    if not reader:
                        # Make sure that ref wasn't previously added as a reader
                        if self.scoreboard.changeToWriter(var, scheduleNode) == False:
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
            lookup.addWaiter(var, scheduleNode, reader)
        else:
            # We have the value
            scheduleNode.setInVarVal(var, lookup)
            if isinstance(lookup, agentgraph.core.mutable.ReadOnly):
                lookup = lookup.getMutable()
                reader = True
            elif isinstance(lookup, agentgraph.core.mutable.ReadOnly):
                lookup = lookup._mutable
                reader = True
            
            if isinstance(lookup, agentgraph.core.mutable.Mutable):
                # If the variable is mutable, add ourselves.
                try:
                    depCount += self.handleReference(scheduleNode, var, lookup, reader)
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
                
            nextNode = node.getNext(0)
            if nextNode is not None:
                #Keep traversing current list
                node = nextNode
            else:
                # Remove current task
                task = self.startTasks
                assert task is not None
                self.startTasks = task.getNext()
                if self.startTasks is None:
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

    def handleReference(self, scheduleNode: ScheduleNode, var: Var, lookup, reader: bool) -> int:
        """We have a variable that references a mutable object.  So the
        variable has to be defined and we need to run it through the
        scoreboard to make sure all prior mutations are done.  This
        function returns the number of unresolved dependences due to
        this heap dependency."""
        if (scheduleNode.addRef(lookup) == False):
            if not reader:
                if self.scoreboard.changeToWriter(lookup, scheduleNode):
                    return 0
                else:
                    return 1
        if reader:
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

        oldWindowSize = self.windowSize
        self.windowSize = oldWindowSize - 1
        if oldWindowSize == 1:
            with self.sleepVar:
                self.sleepVar.notify_all()
        
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
            for n, reader in wlist:
                #Forward value
                n.setInVarVal(var, val)
                if isinstance(val, agentgraph.core.mutable.Mutable):
                    #If variable is mutable, register the heap dependence
                    if self.handleReference(n, var, val, reader) == 0:
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


        if self.windowSize < agentgraph.config.MAX_WINDOW_SIZE and self.windowStall is not None:
            if self.windowStall is not None:
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

        with self.parent.lock:
            self.parent.completed(scheduleNode)
        with self.parent.childrenLock:
            self.parent.children.remove(self)


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
            firstNode = graphnode.getStart()
            assert firstNode is not None
            child.addTask(firstNode, None, varMap = inVarMap)
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
            with self.sleepVar:
                while self.windowSize != 0:
                    self.sleepVar.wait()
            # All good, shutdown the system
            self.engine.shutdown()
            if agentgraph.config.VERBOSE > 0:
                self.getDefaultModel().print_statistics()
