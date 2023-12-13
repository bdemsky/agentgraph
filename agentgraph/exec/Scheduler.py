import asyncio
from agentgraph.exec.Engine import Engine
from agentgraph.graph.Graph import GraphNested, GraphNode
from agentgraph.graph.Var import Var


class ScheduleNode:
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

        
class Scheduler:
    """Scheduler class.  This does all of the scheduling for a given Nested Graph."""
    def __init__(self, scope: GraphNested, varMap: dict, parent: 'Scheduler', engine: Engine):
        self.scope = scope
        self.varMap = varMap
        self.engine = engine
        self.parent = parent
        
    def scan(self, node: GraphNode):
        while True:
            depCount = 0
            inVars = node.readsVars()
            outVars = node.writesVars()
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
                if (n.decDepCount()):
                    # ready to run this one now
                    startTask(n)

    def startTask(self, node: ScheduleNode):
        if isinstance(node, GraphNodeBranch):
            node = node.getNext(node.varMap[node.getGraphNode().getBranchVar()])
            self.scan(node)
        elif node == self.scope:
            if self.parent != None:
                self.parent.completed(node)
            else:
                pass
                #TODO:
        elif isinstance(node, GraphNested):
            # Need start new Scheduler
            child = Scheduler(node, node.getInVarMap(), self, self.engine)
            child.scan(node.getStart())
        else:
            #Schedule the job
            self.engine.queueItem(node)

