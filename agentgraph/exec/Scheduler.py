import asyncio
from agentgraph.exec.Engine import Engine
from agentgraph.graph.Graph import GraphNested, GraphNode
from agentgraph.graph.Var import Var


class ScheduleNode:
    """Schedule node to track dependences for a task instance."""
    
    def __init__(self, node: GraphNode):
        self.node = node
        self.waitMap = dict()
        self.inVarMap = dict()
        self.depCount = 0
        self.refs = {}

    def addRef(self, ref) -> bool:
        """Keeps track of the heap references this task will use.  If
        we see the same reference multiple times, return false on the
        duplicates"""
        
        if ref in self.refs:
            return False
        refs.add(ref)
        return True
        
    def setDepCount(self, depCount: int):
        """Sets Dependency count"""
        
        self.depCount = depCount

    def decDepCount(self) -> bool:
        """Decrement the outstanding dependence count.  If it hits
        zero, then we are ready to run."""
        
        count = self.decCount - 1
        self.decCount = count;
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
        
    async def run(self):
        """Run the node"""
        
        self.outVarMap = await self.node.execute(self.getInVarMap())


class ScoreBoardNode:
    """ScoreBoard linked list node to track heap dependences."""

    def __init__(self, isRead: bool):
        """Create a new scoreboard node.  The isRead parameter is
        True is this is a reader node and false if it is a writer
        node."""
        
        self.isReader = isReader
        self.waiters = {}
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

    def getWaiters() -> list:
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
        scoreboardnode = ScoreBoardNode(false)
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
        self.count = 0
        self.scoreboard = ScoreBoard()
        
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
                        depCount += handleReference(scheduleNode, var, lookup)
                        
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
                node = node.getNext(scheduleNode.varMap[node.getBranchVar()])
            else:
                node = node.getNext(0)


    def handleReference(self, scheduleNode: ScheduleNode, var:Var, lookup) -> int:
        """We have a variable that references a mutable object.  So the
        variable has to be defined and we need to run it through the
        scoreboard to make sure all prior mutations are done.  This
        function returns the number of unresolved dependences due to
        this heap dependency."""
        
        if (scheduleNode.addRef(loop)):
            return 0

        if var.isRead():
             if self.addReader(lookup, scheduleNode):
                 return 0
             else:
                 return 1
        if self.addWriter(lookup, scheduleNode):
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
                if var.isMutable:
                    #If variable is mutable, register the heap dependence
                    if handleReference(n, var, val) == 0:
                        #Only do decrement if we didn't just transfer the count to a heap dependence
                        decDepCount(n)
                else:
                    #No heap dependence, so decrement count
                    decDepCount(n)`
                
        #Release our heap dependences
        inVarValMap = node.getInVarVals()
        for var, val in inVarValMap:
            if var.isMutable():
                self.scoreboard.removeWaiter(val, node, self)
            
        
    def decDepCount(self, node: ScheduleNode):
        """Decrement dependence count.  Starts task if dependence
        count gets to zero."""
        
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
