import asyncio
from agentgraph.graph.BoolVar import BoolVar
from agentgraph.graph.LLMModel import LLMModel
from agentgraph.graph.Var import Var
from agentgraph.graph.Conversation import Conversation

class GraphNode:
    """Base Node For Nested CFG Representation of Program"""
    
    def __init__(self):
        self.next = []

    def setNext(self, index: int, n: 'GraphNode'):
        self.next[index] = n

    def getReadVars(self) -> list:
        return []

    def getWriteVars(self) -> list:
        return []
    
class GraphNested(GraphNode):
    """Nested CFG Node.  Used for control flow constructs such as
    If-Then-Else or a Loop."""
    
    def __init__(self, _start: GraphNode):
        super().__init__()
        self.start = _start
        self.readVars = None
        self.writeVars = None

    def getStart(self) -> GraphNode:
        return self.start

    def getReadVars(self) -> list:
        return self.readVars
        
    def getWriteVars(self) -> list:
        return self.writeVars
    
    def setReadVars(self, readVars: list):
        self.readVars = readVars
        
    def setWriteVars(self, writeVars: list):
        self.writeVars = writeVars
    
class GraphLLMAgent(GraphNode):
    """Run some action.  This is a LLM Agent."""
    
    def __init__(self, model: LLMModel, conversation: Conversation, formatFunc, promptFile: str, outVar: Var, inVars: dict):
        super().__init__()
        self.model = model
        self.conversation = conversation
        self.formatFunc = formatFunc
        self.promptFile = promptFile
        self.outVar = outVar
        self.inVars = inVars if inVars != None else {}

    def getReadVars(self) -> list:
        return self.inVars.values()
        
    def getWriteVars(self) -> list:
        return [self.outVar]

    async def execute(self, varMap: dict) -> dict:
        """ Actually execute LLM Agent."""

        # First, compose dictionary for inVars (str -> Var) and varMap
        # (Var -> Value) to generate inMap (str -> Value)
        
        inMap = dict()
        for name, var in self.inVars:
            inMap[name] = varMap[var]
        
        # Next, actually call the formatFunc to generate the prompt
        output = await self.formatFunc(inMap)

        # Call the model
        outStr = await self.model.sendData(output)

        # Put result in output map
        outMap = dict()
        outMap[self.outVar] = outStr
        
        return outMap
        
class GraphPythonAgent(GraphNode):
    """Run some action.  This is a Python Agent."""
    
    def __init__(self, pythonFunc, inVars: dict, outVars: dict):
        super().__init__()
        self.pythonFunc = pythonFunc
        self.inVars = inVars if inVars != None else {}
        self.outVars = outVars if outVars != None else {}

    def getReadVars(self) -> list:
        return self.inVars.values()
        
    def getWriteVars(self) -> list:
        return self.outVars.values()

    async def execute(self, varMap: dict) -> dict:
        """ Actually execute Python Agent."""

        # First, compose dictionary for inVars (str -> Var) and varMap
        # (Var -> Value) to generate inMap (str -> Value)
        
        inMap = dict()
        for name, var in self.inVars:
            inMap[name] = varMap[var]
        
        # Next, actually call the formatFunc to generate the prompt
        omap = await self.pythonFunc(inMap)


        # Construct outMap (Var -> Object) from outVars (name -> Var)
        # and omap (name -> Value)
        
        outMap = dict()
        if self.outVars != None:
            for name, var in self.outVars:
                outMap[var] = omap[name]
            
        return outMap
    
class GraphNodeNop(GraphNode):
    """Create a Nop Node."""
    
    def __init__(self):
        super().__init__()

class GraphNodeBranch(GraphNode):
    """Conditional branch node."""
    
    def __init__(self, branchVar):
        super().__init__()
        self.branchVar = branchVar
        
    def getBranchVar(self) -> BoolVar:
        return self.branchVar

    def getReadVars(self) -> list:
        return [self.branchVar]
    
class GraphPair:
    """Stores the beginning and end node of a sub graph"""
    
    def __init__(self, start: GraphNode, end: GraphNode):
        self.start = start
        self.end = end

def checkInVars(inVars: dict):
    if inVars == None:
        return
    mutSet = {}
    for v, var in inVars:
        if var.isMutable():
            mutSet.add(var)
    for v, var in inVars:
        if var.isMutable() and var.isRead() and var.getVar() in mutSet:
            raise RuntimeException(f"Snapshotted and mutable versions of {var.getVar().getName()} used by same task.")
    

def createLLMAgent(model: LLMModel, conversation: Conversation, formatFunc, promptFile: str, outVar: Var, inVars: dict = None) -> GraphPair:
    llmAgent = GraphLLMAgent(model, conversation, formatFunc, promptFile, outVar, inVars)
    return GraphPair(llmAgent, llmAgent)

def createPythonAgent(pythonFunc, inVars: dict = None, outVars: dict = None) -> GraphPair:
    pythonAgent = GraphPythonAgent(pythonFunc, inVars, outVars)
    return GraphPair(pythonAgent, pythonAgent)
    
def createSequence(list) -> GraphPair:
    """This creates a sequency of GraphNodes"""
    
    start = list[0].start
    last = list[0].end
    for l in list[1:]:
        last.setNext(0, l.start)
        last = l.end
    return GraphPair(start, last)

def createDoWhile(compute: GraphPair, branchvar: BoolVar) -> GraphPair:
    """This creates a do while loop."""
    
    branch = GraphNodeBranch(branchvar)
    graph = GraphNested(compute.start)
    compute.end.setNext(0, branch)

    #Analyze read/write vars while we still have a linear structure
    readSet, writeSet = analyzeLinear(compute.start, branch)

    #Finish graph
    branch.setNext(1, compute.start)
    branch.setNext(0, graph)

    #Save variable read/write results
    graph.setReadVars(readSetThen)
    graph.setWriteVars(writeSetThen)
    
    return GraphPair(graph, graph)

def createIfElse(condvar: BoolVar, thenN: GraphPair, elseN: GraphPair) -> GraphPair:
    """This creates an if then else block."""
    
    # Analyze variable reads/writes
    readSetThen, writeSetThen = analyzeLinear(thenN[0], thenN[1])
    readSetElse, writeSetElse = analyzeLinear(elseN[0], elseN[1])
    branch = GraphNodeBranch(condvar)
    graph = GraphNested(branch)
    branch.setNext(0, elseN.start)
    branch.setNext(1, thenN.start)
    thenN.last.setNext(0, graph)
    elseN.last.setNext(0, graph)

    #Combine variable reads/writes
    readSetThen.update(readSetElse)
    writeSetThen.update(writeSetElse)
    readSetThen.add(condvar)

    #Save variable read/write results
    graph.setReadVars(readSetThen)
    graph.setWriteVars(writeSetThen)
    
    return GraphPair(graph, graph)

def analyzeLinear(start: GraphNode, end: GraphNode) -> tuple[set, set]:
    """ This function analyzes reads/writes of linear chains"""
    
    node = start
    list = []
    while node != None:
        list.append(node)
        node = node.getNext(0)
    readSet = {}
    writeSet = {}
    for i in range(len(list) - 1, -1, -1):
        n = list[i]
        writeSet.update(n.getWriteSet())
        readSet.difference_update(n.getWriteSet())
        readSet.update(n.getReadSet())
        
    return (readSet, writeSet)
