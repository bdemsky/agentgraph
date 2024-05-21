import asyncio
import contextvars
import sys
import threading
import traceback
import time
from typing import Any, Dict, List, Optional, Set, Union

from agentgraph.exec.engine import Engine, threadrun
from agentgraph.core.graph import VarMap, GraphNested, GraphNode, GraphPythonAgent, GraphVarWait, create_python_agent, create_llm_agent
from agentgraph.core.var import Var
from agentgraph.core.vardict import VarDict
from agentgraph.core.varset import VarSet
from agentgraph.core.msgseq import MsgSeq
from agentgraph.core.tools import Tool
from agentgraph.core.llmmodel import LLMModel
import agentgraph.config

currentTask = contextvars.ContextVar('currentTask', default = None)
currentScheduler = contextvars.ContextVar('scheduler', default = None)
isAsync = contextvars.ContextVar('isAsync', default = False)

def _set_async(status: bool):
    isAsync.set(status)

def _get_async():
    return isAsync.get()


def _get_current_task():
    return currentTask.get()

def _set_current_task(task):
    currentTask.set(task)

def _get_current_scheduler():
    return currentScheduler.get()

def _set_current_scheduler(scheduler):
    currentScheduler.set(scheduler)

class ScheduleNode:
    """Schedule node to track dependences for a task instance."""
    
    def __init__(self, node: GraphNode, id: int):
        self.node = node
        self._wait_map: Dict[Var, list]  = dict()
        self.inVarMap: Dict[Var, Any] = dict()
        self.depCount = 0
        self.refs: Set['agentgraph.core.mutable.Mutable'] = set()
        self.id = id
        
    def _add_ref(self, ref) -> bool:
        """Keeps track of the heap references this task will use.  If
        we see the same reference multiple times, return false for the
        duplicates"""
        
        root = ref._get_root_object()
        if root in self.refs:
            return False
        self.refs.add(root)
        return True

    def _get_refs(self) -> set:
        return self.refs
   
    def _get_id(self) -> int:
        return self.id

    def assertOwnership(self):
        for ref in self.refs:
            if isinstance(ref, agentgraph.core.mutable.Mutable):
                ref.set_owning_task(self)
                
    def _set_dep_count(self, depCount: int):
        """Sets Dependency count"""
        
        self.depCount = depCount

    def _dec_dep_count(self) -> bool:
        """Decrement the outstanding dependence count.  If it hits
        zero, then we are ready to run."""
        
        count = self.depCount - 1
        self.depCount = count;
        return count == 0

    def _get_graph_node(self) -> GraphNode:
        """Returns the underlying graph node this task will execute."""
        
        return self.node

    def _add_waiter(self, var: Var, node, reader: bool):
        """Add a schedulenode that is waiting on us for value of the
        variable var and whether it is a reader."""
        
        if var in self._wait_map:
            list = self._wait_map[var]
        else:
            list = []
            self._wait_map[var] = list
        list.append((node, reader))

    def _get_waiters(self) -> dict:
        """Returns a map of waiters.  This maps maps our output
        variables to the set of schedule nodes that need that value
        from us."""
        
        return self._wait_map

    def _set_out_var_map(self, outVarMap: dict):
        self.outVarMap = outVarMap

    def _get_out_var_map(self):
        return self.outVarMap
    
    def _get_out_var_val(self, var: Var):
        """Returns the output value for the variable var."""
        
        return self.outVarMap[var]

    def _set_in_var_val(self, var: Var, val):
        """Returns the input value for the variable var.  If we are
        still waiting on that value, then it will return the
        ScheduleNode that will provide the value."""

        self.inVarMap[var] = val

    def _get_in_var_map(self):
        """Returns the inVarMap mapping."""
        
        return self.inVarMap
        
    async def run(self):
        """Run the node"""
        self.outVarMap = await self.node.execute(self._get_in_var_map())

    def _thread_run(self, scheduler: 'Scheduler'):
        """Run the node"""
        assert isinstance(self.node, agentgraph.core.graph.GraphPythonAgent)
        self.outVarMap = self.node.execute(scheduler, self._get_in_var_map())

_dummy_task = ScheduleNode(GraphNode(), 0)
            
class ScoreBoardNode:
    """ScoreBoard linked list node to track heap dependences."""

    def __init__(self, is_reader: bool):
        """Create a new scoreboard node.  The is_read parameter is
        True is this is a reader node and false if it is a writer
        node."""
        
        self.is_reader = is_reader
        self.waiters: Set[ScheduleNode] = set()
        self.next: Optional['ScoreBoardNode'] = None
        self.pred: Optional['ScoreBoardNode'] = None
        self.idRange: Optional[tuple[int, int]] = None

    def clear_pred(self):
        self.pred = None

    def _get_idRange(self) -> tuple[int, int]:
        range = self.idRange
        assert range is not None
        return range

    def get_is_reader(self) -> bool:
        """Returns true if the node in question is for readers."""

        return self.is_reader

    def set_next(self, next: 'ScoreBoardNode'):
        """Sets the next scoreboard node."""
        
        self.next = next
        next.pred = self

    def _get_pred(self) -> Optional['ScoreBoardNode']:
        """Returns the previous scoreboard node."""

        return self.pred

    def get_next(self) -> Optional['ScoreBoardNode']:
        """Returns the next scoreboard node."""

        return self.next
        
    def _add_waiter(self, waiter: ScheduleNode):
        """Adds a waiter to this scoreboard node."""

        range = self.idRange
        if range is None:
            self.idRange = waiter.id, waiter.id
        else:
            self.idRange = min(range[0], waiter.id), max(range[1], waiter.id)
        self.waiters.add(waiter)

    def _get_waiters(self) -> Set[ScheduleNode]:
        """Returns a list of waiting ScheduleNodes for this scoreboard
        node."""
        
        return self.waiters

    @staticmethod
    def split_node(reader: 'ScoreBoardNode', writer: 'ScoreBoardNode') -> tuple['ScoreBoardNode', 'ScoreBoardNode']:
        # writer node should have a single id for id range
        writer_id = writer._get_idRange()[0]
        before_write, after_write = ScoreBoardNode(True), ScoreBoardNode(True)
        for waiter in reader.waiters:
            if waiter._get_id() < writer_id:
                before_write._add_waiter(waiter)
            elif waiter._get_id() > writer_id:
                after_write._add_waiter(waiter)

        # in case the writer is at the start or end of the reader
        # id range and the before/after node is empty
        if before_write.idRange != None:
            before_write.set_next(writer)
        else:
            before_write = writer
        
        if after_write.idRange != None:
            writer.set_next(after_write)
        else:
            after_write = writer

        return before_write, after_write


    @staticmethod
    def merge(this: 'ScoreBoardNode', that: 'ScoreBoardNode') -> tuple['ScoreBoardNode', 'ScoreBoardNode']:
        """merge two nodes with overlapping id ranges. """

        thisRange = this._get_idRange()
        thatRange = that._get_idRange()
        assert thisRange[1] >= thatRange[0] and thatRange[1] >= thisRange[0]

        if this.is_reader and that.is_reader:
            reader = ScoreBoardNode(True)
            reader.waiters = this.waiters | that.waiters
            reader.idRange = min(thisRange[0], thatRange[0]), max(thisRange[1], thatRange[1])
            return reader, reader

        writer = ScoreBoardNode(False)
        if this.is_reader:
            reader = this
            writer.waiters = that.waiters
            writer.idRange = thatRange
        else:
            writer.waiters = this.waiters
            writer.idRange = thisRange
            if that.is_reader:
                reader = that
            else:
                return writer, writer

        return ScoreBoardNode.split_node(reader, writer)

class ScoreBoard:
    """ScoreBoard object to track object dependencies between agents."""
    
    def __init__(self):
        self.accesses = dict()

    def _add_reader(self, object, node: ScheduleNode) -> bool:
        """Add task node with read dependence on object.  Returns True
        if there is no conflict blocking execution."""
        scoreboardnode = ScoreBoardNode(True)
        scoreboardnode._add_waiter(node)

        root = object._get_root_object()
        if root in self.accesses:
            # We have a list of waiters.

            start, end = self.accesses[root]
        else:
            # If we are at the beginning, we can just return true and
            # do the snapshot.
            self.accesses[root] = (scoreboardnode, scoreboardnode)
            return True

        id = node._get_id()
        curr = end

        while curr is not None:
            pred = curr._get_pred()
            if not curr.get_is_reader():
                # Write node...  We should add after as long as our id
                # is larger.
                if curr._get_idRange()[1] < id:
                    oldNext = curr.get_next()
                    curr.set_next(scoreboardnode)
                    if curr == end:
                        self.accesses[root] = (start, scoreboardnode)
                    else:
                        scoreboardnode.set_next(oldNext)

                    return False
            else:
                # Read node, can add as long as we should not be ahead
                # of its predecessor
                if pred is None or pred._get_idRange()[1] < id:
                    curr._add_waiter(node)
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

            
    def _add_writer(self, object, node: ScheduleNode) -> bool:
        """Add task node with write dependence on object.  Returns
        True if there is no conflict blocking execution."""
        
        # Create a new scoreboard node for writing and add ourselves to
        # it.
        scoreboardnode = ScoreBoardNode(False)
        scoreboardnode._add_waiter(node)
        
        root = object._get_root_object()
        if root in self.accesses:
            # Already have a linked list, so add ourselves to it.
            start, end = self.accesses[root]
        else:
            # We are the first node.
            self.accesses[root] = (scoreboardnode, scoreboardnode)
            return True

        id = node._get_id()
        curr = end

        while curr is not None:
            range = curr._get_idRange()
            if id > range[1]:
                oldNext = curr.get_next()
                curr.set_next(scoreboardnode)
                if curr == end:
                    self.accesses[root] = (start, scoreboardnode)
                else:
                    scoreboardnode.set_next(oldNext)
                return False
            elif id > range[0]:
                # We have a write splitting a read node...
                first, last = ScoreBoardNode.split_node(curr, scoreboardnode)
                pred = curr._get_pred()
                succ = curr.get_next()
                if pred is None:
                    # This case shouldn't be possible, because the
                    # only case where we traverse is for returning a
                    # mutable references, and a reader shouldn't be
                    # able to provide a reference to some later
                    # writer...
                    raise RuntimeError("Predecessor should never be None")

                pred.set_next(first)

                if succ is None:
                    self.accesses[root] = (start, last)
                    return False
                else:
                    last.set_next(succ)
                return False

            curr = curr._get_pred()

        # BD: I don't think this case is actually possible since the
        # only case where we are not added at the end is if there is a
        # variable resolution.  But then we should be after the
        # variable assignment task, and it has not released its heap
        # references yet.
        raise RuntimeError("Impossible case")


    def _change_to_writer(self, object, node: ScheduleNode):
        """Change existing node from reader to writer. Returns
        True if there is no conflict blocking execution or if
        no change was made."""
        root = object._get_root_object()
        # Reference should already been previously added
        start, end = self.accesses[root]

        id = node._get_id()
        curr = end

        while curr is not None:
            range = curr._get_idRange()
            if id > range[1]:
                raise RuntimeError("Impossible case")
            elif id >= range[0]:
                assert node in curr._get_waiters()
                if not curr.get_is_reader():
                    # Node was already a writer
                    return True
                if len(curr._get_waiters()) == 1:
                    # Schedule node is the only one, just change node to writer
                    curr.is_reader = False
                    return True
                
                # Split the node
                scoreboardnode = ScoreBoardNode(False)
                scoreboardnode._add_waiter(node)
                first, last = ScoreBoardNode.split_node(curr, scoreboardnode)
                pred = curr._get_pred()
                succ = curr.get_next()
                if pred is None:
                    self.accesses[root] = (first, end)
                else:
                    pred.set_next(first)

                if succ is None:
                    self.accesses[root] = (first if pred is None else start, last)
                else:
                    last.set_next(succ)
                # Return false if it now has to wait since it is no longer a reader
                # unless it previously was already waiting
                return start != curr or first != scoreboardnode

            curr = curr._get_pred()

        raise RuntimeError("Impossible case")


    def _remove_waiter(self, object, node: ScheduleNode, scheduler: 'Scheduler') -> bool:
        """Removes a waiting schedulenode from the list.  Returns
        false if that node had already cleared this queue and true if
        it was still waiting."""
        root = object._get_root_object()
        first, last = self.accesses[root]
        if node in first._get_waiters():
            first._get_waiters().remove(node)
            if len(first._get_waiters()) == 0:
                if first == last:
                    del self.accesses[root]
                else:
                    newfirst = first.get_next()
                    newfirst.clear_pred()
                    self.accesses[root] = (newfirst, last)
                    #Update scheduler
                    for nextnode in newfirst._get_waiters():
                        scheduler._dec_dep_count(nextnode)
            return False
        else:
            # BCD: Can this branch ever be called??
            entry = first.get_next()
            prev = first
            while entry is not None:
                if node in entry._get_waiters():
                    entry._get_waiters().remove(node)
                    if len(entry._get_waiters()) == 0:
                        entry.clear_pred()
                        prev.set_next(entry.get_next())
                        #See if we eliminated tail and thus need to update queue
                        if last == entry:
                            self.accesses[root] = (first, prev)
                    break
                prev = entry
                entry = entry.get_next()
            return True

    def _merge_access_queues(self, source, dest):
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

        if srcNode._get_idRange()[1] < dstNode._get_idRange()[0]:
            first = curNode = srcNode
            srcNode = srcNode.get_next()
        elif dstNode._get_idRange()[1] < srcNode._get_idRange()[0]:
            first = curNode = dstNode
            dstNode = dstNode.get_next()
        else:
            first, curNode = ScoreBoardNode.merge(srcNode, dstNode)
            srcNode = srcNode.get_next()
            dstNode = dstNode.get_next()

        while srcNode is not None and dstNode is not None:
            if srcNode._get_idRange()[1] < dstNode._get_idRange()[0]:
                curNode.set_next(srcNode)
                curNode = srcNode
                srcNode = srcNode.get_next()
            elif dstNode._get_idRange()[1] < srcNode._get_idRange()[0]:
                curNode.set_next(dstNode)
                curNode = dstNode
                dstNode = dstNode.get_next()
            else:
                start, end = ScoreBoardNode.merge(srcNode, dstNode)
                curNode.set_next(start)
                curNode = end
                srcNode = srcNode.get_next()
                dstNode = dstNode.get_next()
        
        if srcNode is not None:
            curNode.set_next(srcNode)
            last = srcLast
        elif dstNode is not None:
            curNode.set_next(dstNode)
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

    def set_next(self, next: 'TaskNode'):
        self.next = next

    def get_next(self) -> Optional['TaskNode']:
        return self.next
        
    def get_var_map(self) -> dict:
        return self.varMap

    def get_node(self) -> GraphNode:
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
        self.start_tasks: Optional[TaskNode] = None
        self.endTasks: Optional[TaskNode] = None
        self.lock = threading.Lock()
        self.condVar = threading.Condition()
        self.sleepVar = threading.Condition()
        self.dummyVar = Var("Dummy$$$$$")
        self.nextId = 1
        self.children: Set['Scheduler'] = set()
        self.childrenLock = threading.Lock()

    def _get_new_id(self) -> int:
        id = self.nextId
        self.nextId += 1
        return id

    def get_default_model(self) -> LLMModel:
        return self.model
        
    def _merge_obj_accesses(self, source, dest):
        """
        merge accesses from object source in current and all parent schedulers
        """
        scheduler = self
        while scheduler is not None:
            with scheduler.lock:
                scheduler.scoreboard._merge_access_queues(source, dest)
            scheduler = scheduler.parent
        
    def obj_access(self, mutable, readonly=False):
        """
        Waits for object access
        """
        gvar = GraphVarWait([self.dummyVar], self.condVar)
        varDict = dict()
        if readonly:
            varDict[self.dummyVar] = agentgraph.core.mutable.ReadOnly(mutable._get_root_object())
        else:
            varDict[self.dummyVar] = mutable._get_root_object()
        self.add_task(gvar, None, varDict)
        self._wait_on_var_wait(gvar)
        
    def read_variable(self, var: Var):
        """
        Reads value of variable, stalling if needed.
        """
        
        gvar = GraphVarWait([var], self.condVar)
        self.add_task(gvar)
        #Wait for our task to finish
        self._wait_on_var_wait(gvar)
        return gvar[var]
    
    def _wait_on_var_wait(self, gvar):
        """
        Wait for condVar or steal a child task on timeout.
        """
        with self.condVar:
            while not gvar.is_done():
                if self.engine._get_pending_python_task_count() > 0:
                    self.condVar.release()
                    taskStolen = False
                    try:
                        taskStolen = self._steal_child_task()
                    finally:
                        self.condVar.acquire()
                        # Make sure we didn't miss the event while we
                        # tried to steal task.
                        if gvar.is_done():
                            return
                        # If we stole a task successfully, loop again
                        # without waiting
                        if taskStolen:
                            continue
                # Did not successfully steal task, so wait and give up lock
                self.condVar.wait(timeout=0.01)

    def _steal_child_task(self) -> bool:
        child = self._get_pending_child()
        if child:
            threadrun(self.engine, child.scope, child)
            _set_current_scheduler(self)
            return True
        else:
            return False

    def _get_pending_child(self):
        """
        Find a child task that has not started running.
        """
        with self.childrenLock:
            for child in self.children:
                if child.future.cancel():
                    return child
                descendent = child._get_pending_child()
                if descendent is not None:
                    return descendent


    def add_task(self, node: GraphNode, vm: Optional[VarMap] = None, varMap: Optional[dict] = None):
        """
        Adds a new task for the scheduler to run.
        node - a GraphNode to run
        varMap - a map of Vars to values
        """

        if vm is not None:
            varMap = vm.get_var_map()
        if varMap is None:
            varMap = dict()
        taskNode = TaskNode(node, varMap)

        if self.endTasks is None:
            self.start_tasks = taskNode
        else:
            self.endTasks.set_next(taskNode)

        self.endTasks = taskNode
        with self.lock:
            self._finish_add_task(varMap, node)

    def _finish_add_task(self, varMap: dict, node: GraphNode):
        self._check_for_mutables(node, varMap)
        
        if (self.start_tasks == self.endTasks):
            runTask = self.endTasks
            assert runTask is not None
            self._run_task(runTask)
            
    def _check_var_for_mutable(self, varMap: dict, writeSet: Set[Var], currSchedulerTask: ScheduleNode, v):
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
            mutTask = value.get_owning_task()
            # See if parent owns this Mutable.  If so, we know
            # there will be no race when we revoke ownership
            # by setting the owner to _dummy_task.  If the
            # parent doesn't own the Mutable, it won't be
            # racing with children, and so we have no problem.
            if mutTask == currSchedulerTask:
                value.set_owning_task(_dummy_task)
            
    def _check_for_mutables(self, node: Optional[GraphNode], varMap: dict):
        """
        Handle and references to mutable objects.  If a mutable
        object is owned by the parent task, revoke ownership.
        """

        writeSet: Set[Var] = set()
        currSchedulerTask = _get_current_task()
        while node is not None:
            for var in node._get_read_set():
                if isinstance(var, VarDict):
                    for v in var.values():
                        self._check_var_for_mutable(varMap, writeSet, currSchedulerTask, v)
                elif isinstance(var, VarSet):
                    for v in var:
                        self._check_var_for_mutable(varMap, writeSet, currSchedulerTask, v)
                else:
                    self._check_var_for_mutable(varMap, writeSet, currSchedulerTask, var)
                    
            writeSet.update(node.get_write_vars())
            node = node.get_next(0)


    def _run_task(self, task: TaskNode):
        """Starts up the first task."""

        # Update scheduler variable map with task variable map...
        for var in task.get_var_map():
            value = task.get_var_map()[var]
            self.varMap[var] = value

        self.scan(task.get_node())

    def run_python_agent(self, pythonFunc, pos: Optional[list] = None, kw: Optional[dict] = None, numOuts: int = 0, vmap: Optional[VarMap] = None):
        out = None
        if numOuts > 0:
            out = list()
            for v in range(numOuts):
                out.append(agentgraph.Var())
        self.add_task(create_python_agent(pythonFunc, pos, kw, out).start, vmap)
        if numOuts == 1:
            return out[0]
        return out
        
    def run_llm_agent(self, msg: Optional[MsgSeq] = None, conversation: Union[Var, None, 'agentgraph.core.conversation.Conversation'] = None, tools: Optional['agentgraph.core.tools.ToolList'] = None, formatFunc = None, pos: Optional[list] = None, kw: Optional[dict] = None, llmopts: Optional[dict] = None, model: Optional[LLMModel] = None, vmap: Optional[VarMap] = None):
        outVar = Var()
        if tools is not None:
            callVar = Var()
        else:
            callVar = None
        self.add_task(create_llm_agent(outVar, msg, conversation, callVar, tools, formatFunc, pos, kw, llmopts, model).start, vmap)
        if tools is not None:
            return outVar, callVar
        else:
            return outVar

    def check_finish_scope(self):
        if self.windowSize == 0:
            self._finish_scope()

    def _scan_node_var(self, node: GraphNode, scheduleNode: ScheduleNode, var, depCount: int) -> int:
        if isinstance(var, agentgraph.core.mutable.ReadOnly):
            var = var.get_mutable()
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
                if scheduleNode._add_ref(var):
                    if reader:
                        if self.scoreboard._add_reader(var, scheduleNode) == False:
                            depCount += 1
                    else:
                        if self.scoreboard._add_writer(var, scheduleNode) == False:
                            depCount += 1
                else:
                    if not reader:
                        # Make sure that ref wasn't previously added as a reader
                        if self.scoreboard._change_to_writer(var, scheduleNode) == False:
                            depCount += 1
            return depCount

        if var not in self.varMap:
            varName = var.get_name()
            raise RuntimeError(f"Use before define with {varName}")
                    
        lookup = self.varMap[var]
        if isinstance(lookup, ScheduleNode):
            # Variable mapped to schedule node, which means we
            # haven't executed the relevant computation
            depCount += 1
            lookup._add_waiter(var, scheduleNode, reader)
        else:
            # We have the value
            scheduleNode._set_in_var_val(var, lookup)
            if isinstance(lookup, agentgraph.core.mutable.ReadOnly):
                lookup = lookup.get_mutable()
                reader = True
            elif isinstance(lookup, agentgraph.core.mutable.ReadOnly):
                lookup = lookup._mutable
                reader = True
            
            if isinstance(lookup, agentgraph.core.mutable.Mutable):
                # If the variable is mutable, add ourselves.
                try:
                    depCount += self._handle_reference(scheduleNode, var, lookup, reader)
                except Exception as e:
                    print('Error', e)
                    print(traceback.format_exc())
                    return depCount
        return depCount
                    
    def scan(self, node: GraphNode):
        """Scans nodes in graph for scheduling purposes."""
        while True:
            if self.scope is not None and node == self.scope._get_graph_node():
                print("BAD")
                return
            depCount = 0
            inVars = node._get_read_set()
            outVars = node.get_write_vars()

            scheduleNode = ScheduleNode(node, self._get_new_id())

            # Compute our set of dependencies
            for var in inVars:
                if isinstance(var, VarDict):
                    for v in var.values():
                        depCount = self._scan_node_var(node, scheduleNode, v, depCount)
                elif isinstance(var, VarSet):
                    for v in var:
                        depCount = self._scan_node_var(node, scheduleNode, v, depCount)
                else:
                    depCount = self._scan_node_var(node, scheduleNode, var, depCount)

            # Save our dependence count.
            scheduleNode._set_dep_count(depCount)

            # Update variable map with any of our dependencies
            for var in outVars:
                self.varMap[var] = scheduleNode

            #Compute next node to scan
            self.windowSize += 1
            if (depCount == 0):
                self.start_nested_task(scheduleNode)
                
            nextNode = node.get_next(0)
            if nextNode is not None:
                #Keep traversing current list
                node = nextNode
            else:
                # Remove current task
                task = self.start_tasks
                assert task is not None
                self.start_tasks = task.get_next()
                if self.start_tasks is None:
                    # No more work left so return
                    self.endTasks = None
                    return
                else:
                    # Start scheduling next task
                    nexttask = self.start_tasks
                    node = nexttask.get_node()
                    for var in nexttask.get_var_map():
                        value = nexttask.get_var_map()[var]
                        self.varMap[var] = value   

    def _handle_reference(self, scheduleNode: ScheduleNode, var: Var, lookup, reader: bool) -> int:
        """We have a variable that references a mutable object.  So the
        variable has to be defined and we need to run it through the
        scoreboard to make sure all prior mutations are done.  This
        function returns the number of unresolved dependences due to
        this heap dependency."""
        if (scheduleNode._add_ref(lookup) == False):
            if not reader:
                if self.scoreboard._change_to_writer(lookup, scheduleNode):
                    return 0
                else:
                    return 1
        if reader:
            if self.scoreboard._add_reader(lookup, scheduleNode):
                return 0
            else:
                return 1
        if self.scoreboard._add_writer(lookup, scheduleNode):
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
            self.check_finish_scope()
            return
        
        # Get list of tasks waiting on variables
        waiters = node._get_waiters()
        for var in waiters:
            # Get value  of output variable
            val = node._get_out_var_val(var)
            # Get list of waiters
            wlist = waiters[var]
            for n, reader in wlist:
                #Forward value
                n._set_in_var_val(var, val)
                if isinstance(val, agentgraph.core.mutable.Mutable):
                    #If variable is mutable, register the heap dependence
                    if self._handle_reference(n, var, val, reader) == 0:
                        #Only do decrement if we didn't just transfer the count to a heap dependence
                        self._dec_dep_count(n)
                else:
                    #No heap dependence, so decrement count
                    self._dec_dep_count(n)

        outVarValMap = node._get_out_var_map()
        if outVarValMap is not None:
            for var in outVarValMap:
                # Pull ourselves out of any varMap entries and replace
                # with value so that future tasks are not waiting on us.
                if self.varMap[var] == node:
                    self.varMap[var] = outVarValMap[var]

        # Release our heap dependences
        refSet = node._get_refs()
        for r in refSet:
            self.scoreboard._remove_waiter(r, node, self)


        if self.windowSize < agentgraph.config.MAX_WINDOW_SIZE and self.windowStall is not None:
            if self.windowStall is not None:
                tmp = self.windowStall
                self.windowStall = None
                self.scan(tmp._get_graph_node())

        #Check if we need to finish scope off
        self.check_finish_scope()
        
    def _dec_dep_count(self, node: ScheduleNode):
        """Decrement dependence count.  Starts task if dependence
        count gets to zero."""
        
        if node._dec_dep_count():
            #Ready to run this one now
            self.start_task(node)

    def _finish_scope(self):
        """Finish off a GraphNested node.  For now we require that all
        child tasks have completed before the nested completes.  More
        sophisticated implementations are possible that allow nodes to
        partially complete.

        """
        
        #See if anyone cares about the end of the scope
        if self.parent is None:
            return
        
        scheduleNode = self.scope
        graphnode = scheduleNode._get_graph_node()

        #Need to build value map to record the values the nested graph outputs
        if not isinstance(graphnode, GraphPythonAgent):
            writeMap = dict()
            writeSet = graphnode.get_write_vars()
            for var in writeSet:
                writeMap[var] = self.varMap[var]
            scheduleNode._set_out_var_map(writeMap)

        with self.parent.lock:
            self.parent.completed(scheduleNode)
        with self.parent.childrenLock:
            self.parent.children.remove(self)


    def start_nested_task(self, scheduleNode: ScheduleNode):
        """Starts task."""
        
        graphnode = scheduleNode._get_graph_node()

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
                    self.engine._thread_queue_item(scheduleNode, child)
                return
            
            inVarMap = scheduleNode._get_in_var_map()            
            child = Scheduler(self.model, scheduleNode, self, self.engine)
            firstNode = graphnode.getStart()
            assert firstNode is not None
            child.add_task(firstNode, None, varMap = inVarMap)
        else:
            #Schedule the job
            self.engine._queue_item(scheduleNode, self)

    def start_task(self, scheduleNode: ScheduleNode):
        """Starts task including conditional branch instruction."""
        
        graphnode = scheduleNode._get_graph_node()
        self.start_nested_task(scheduleNode)

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
                self.get_default_model().print_statistics()
