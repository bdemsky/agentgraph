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

    def getReadVars() -> list:
        return []

    def getWriteVars() -> list:
        return []
    
class GraphNested(GraphNode):
    """Nested CFG Node.  Used for control flow constructs such as If-Then-Else or a Loop."""
    def __init__(self, _start: GraphNode):
        super().__init__()
        self.start = _start
        self.readVars = None
        self.writeVars = None
        self.refs = None
        self.snapshotRefs = None

    def getStart() -> GraphNode:
        return self.start

    def getReadVars() -> list:
        return self.readVars
        
    def getWriteVars() -> list:
        return self.writeVars
    
    def setReadVars(readVars: list):
        self.readVars = readVars
        
    def setWriteVars(writeVars: list):
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

    def getReadVars() -> list:
        return self.inVars.values()
        
    def getWriteVars() -> list:
        return [self.outVar]
    
class GraphPythonAgent(GraphNode):
    """Run some action.  This is a Python Agent."""
    def __init__(self, pythonFunc, inVars: dict, outVars: dict, refs: dict, snapshotRefs: dict):
        super().__init__()
        self.pythonFunc = pythonFunc
        self.inVars = inVars if inVars != None else {}
        self.outVars = outVars if outVars != None else {}
        self.refs = refs if refs != None else {}
        self.snapshotRefs = snapshotRefs if snapshotRefs != None else {}

    def getReadVars() -> list:
        return self.inVars.values()
        
    def getWriteVars() -> list:
        return self.outVars.values()

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

    def getReadVars() -> list:
        return [self.branchVar]
    
class GraphPair:
    """Stores the beginning and end node of a sub graph"""
    def __init__(self, start: GraphNode, end: GraphNode):
        self.start = start
        self.end = end


def createLLMAgent(model: LLMModel, conversation: Conversation, formatFunc, promptFile: str, outVar: Var, inVars: dict = None, refs: dict = None, snapshotRefs: dict = None) -> GraphPair:
    llmAgent = GraphLLMAgent(model, conversation, formatFunc, promptFile, outVar, inVars, refs, snapshotRefs)
    return GraphPair(llmAgent, llmAgent)

def createPythonAgent(pythonFunc, inVars: dict = None, outVars: dict = None, refs: dict = None, snapshotRefs: dict = None) -> GraphPair:
    pythonAgent = GraphPythonAgent(pythonFunc, inVars, outVars, refs, snapshotRefs)
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
