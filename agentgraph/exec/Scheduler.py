import asyncio
from agentgraph.exec.Engine import Engine
from agentgraph.graph.Graph import GraphNested, GraphNode
from agentgraph.graph.Var import Var


class ScheduleNode:
    """Schedule node to track dependences for a tasks."""
    def __init__(self, node: GraphNode, depCount: int, varMap: dict):
        self.node = node
        self.waitMap = dict()
        self.inVarMap = dict()

    def setup(self, depCount: int):
        self.depCount = depCount
        
    def getGraphNode(self) -> GraphNode:
        return self.node

    def addWaiter(self, var: Var, node: 'ScheduleNode'):
        """Add a schedulenode that is waiting on us for value of the variable var."""
        if var in self.waitMap:
            set = self.waitMap[var]
        else:
            set = {}
            self.waitMap[var] = set
        set.add(node)

    def getWaiters(self) -> dict:
        """Returns a map of waiters.  This maps maps our output
        variables to the set of schedule nodes that need that value
        from us."""
        return self.waitMap

    def getOutVarVal(self, var: Var):
        self.outVarMap[var]

    def setInVarVal(self, var: Var, val):
        self.inVarMap[var] = val

    def getInVarMap(self):
        return self.inVarMap
        
    def decDepCount(self) -> bool:
        """Decrement the outstanding dependence count.  If it hits zero, then we are ready to run."""
        count = self.decCount - 1
        self.decCount = count;
        return count == 0

    async def run(self):
        """Run the node"""
        self.outVarMap = await self.node.execute(self.getInVarMap())

class ScoreBoardNode:
    """ScoreBoard node to track heap dependences."""
    def __init__(self, isRead: bool):
        self.isReader = isReader
        self.waiters = {}
        self.next = None
        
    def isReader(self) -> bool:
        return self.isReader

    def setNext(self, next: 'ScoreBoardNode'):
        self.next = next

    def getNext(self) -> 'ScoreBoardNode':
        return self.next
        
    def addWaiter(self, waiter):
        self.waiters.add(waiter)

    def getWaiters() -> list:
        return self.waiters

class ScoreBoard:
    """ScoreBoard object to track object dependencies between agents."""
    def __init__(self):
        self.accesses = dict()

    def addReader(self, object, node: ScheduleNode) -> bool:
        """Add task node with read dependence on object."""
        if object in self.accesses:
            pair = self.accesses[object]
            start = pair[0]
            end = pair[1]
        else:
            return True

        if not end.isReader():
            scoreboardnode = ScoreBoardNode(true)
            scoreboardnode.addWaiter(node)
            end.setNext(scoreboardnode)
            end = scoreboardnode
            self.accesses[object] = (start, end)
        else:
            end.addWaiter(node)
        return False
            
    def addWriter(self, object, node: ScheduleNode) -> bool:
        """Add task node with write dependence on object."""
        scoreboardnode = ScoreBoardNode(false)
        scoreboardnode.addWaiter(node)
        
        if object in self.accesses:
            pair = self.accesses[object]
            pair[1].setNext(scoreboardnode)
            self.accesses[object] = (pair[0], scoreboardnode)
            return False
        else:
            self.accesses[object] = (scoreboardnode, scoreboardnode)
            return True


    def removeWaiter(self, object, node: ScheduleNode, scheduler: 'Scheduler') -> bool:
        """Removes a waiting schedulenode from the list.  Returns
        false if that node had already cleared this queue and true if
        it was still waiting."""
        first, last = self.accesses[object]
        if node in first.getWaiters():
            first.getWaiters().remove(node)
            if len(first).getWaiters() == 0:
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

class Scheduler:
    """Scheduler class.  This does all of the scheduling for a given Nested Graph."""
    def __init__(self, scope: GraphNested, varMap: dict, parent: 'Scheduler', engine: Engine):
        self.scope = scope
        self.varMap = varMap
        self.engine = engine
        self.parent = parent
        
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
                    depCount += 1
                    lookup.addWaiter(var, scheduleNode)
                else:
                    scheduleNode.setInVarVal(var, lookup)
            scheduleNode.setup(depCount)
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
                node = node.getNext(scheduleNode.varMap[node.getBranchVar()])
            else:
                node = node.getNext(0)
            
    def completed(self, node: ScheduleNode):
        waiters = node.getWaiters()
        for var in waiters:
            val = node.getOutVarVal(var)
            set = waiters[var]
            for n in set:
                n.setInVarVal(var, val)
                decDepCount(n)
                    
    def decDepCount(self, node: ScheduleNode):
        """Decrement dependence count."""
        if node.decDepCount():
            #Ready to run this one now
            startTask(node)
                    
    def startTask(self, node: ScheduleNode):
        """Starts task."""
        if isinstance(node, GraphNodeBranch):
            #Process branch task
            node = node.getNext(node.varMap[node.getGraphNode().getBranchVar()])
            self.scan(node)
        elif node == self.scope:
            #Dependences are resolve for final node
            if self.parent != None:
                self.parent.completed(node)
            else:
                pass
        elif isinstance(node, GraphNested):
            # Need start new Scheduler
            child = Scheduler(node, node.getInVarMap(), self, self.engine)
            child.scan(node.getStart())
        else:
            #Schedule the job
            self.engine.queueItem(node)

