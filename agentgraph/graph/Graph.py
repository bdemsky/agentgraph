from agentgraph.graph.BoolVar import BoolVar
from agentgraph.graph.Var import Var
from agentgraph.graph.Conversation import Conversation

class GraphNode:
    """Base Node For Nested CFG Representation of Program"""
    def __init__(self):
        self.next = []

    def setNext(self, index: int, n: 'GraphNode'):
        self.next[index] = n

    def readsVars() -> list:
        return []

    def writesVars() -> list:
        return []
        
class GraphNested(GraphNode):
    """Nested CFG Node.  Used for control flow constructs such as If-Then-Else or a Loop."""
    def __init__(self, _start: GraphNode):
        super().__init__()
        self.start = _start
    def getStart() -> GraphNode:
        return self.start

class GraphLLMAgent(GraphNode):
    """Run some action.  This is a LLM Agent."""
    def __init__(self, conversation: Conversation, inputs: dict, snapshots: dict, format_func, prompt_file: str, output: Var):
        super().__init__()
        self.conversation = conversation
        self.inputs = inputs
        self.snapshots = snapshots
        self.format_func = format_func
        self.prompt_file = prompt_file
        self.output = output

class GraphPythonAgent(GraphNode):
    """Run some action.  This is a Python Agent."""
    def __init__(self, inputs: dict, snapshots: dict, python_func, output: Var):
        super().__init__()
        self.inputs = inputs
        self.snapshots = snapshots
        self.python_func = python_func
        self.output = output

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

    def readsVar() -> list:
        return [self.branchVar]
    
class GraphPair:
    """Stores the beginning and end node of a sub graph"""
    def __init__(self, start: GraphNode, end: GraphNode):
        self.start = start
        self.end = end


def createLLMAgent(convo:Conversation, inputs: dict, snapshots: dict, format_func, prompt_file: str, output: Var) -> GraphPair:
    llmagent = GraphLLMAgent(convo, inputs, snapshots, format_func, prompt_file, output)
    return GraphPair(llmagent, llmagent)

def createPythonAgent(inputs: dict, snapshots: dict, python_func, output: Var) -> GraphPair:
    pythonagent = GraphPythonAgent(inputs, snapshots, python_func, output)
    return GraphPair(pythonagent, pythonagent)
    
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
    branch.setNext(1, compute.start)
    branch.setNext(0, graph)
    return GraphPair(graph, graph)

def createIfElse(condvar: BoolVar, thenN: GraphPair, elseN: GraphPair) -> GraphPair:
    """This creates an if then else block."""
    branch = GraphNodeBranch(condvar)
    graph = GraphNested(branch)
    branch.setNext(0, elseN.start)
    branch.setNext(1, thenN.start)
    thenN.last.setNext(0, graph)
    elseN.last.setNext(0, graph)
    return GraphPair(graph, graph)
