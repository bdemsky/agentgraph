import asyncio
import threading

from agentgraph.core.boolvar import BoolVar
from agentgraph.core.conversation import Conversation
from agentgraph.data.filestore import FileStore
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.msgseq import MsgSeq
from agentgraph.core.mutable import Mutable
from agentgraph.core.mutvar import MutVar
from agentgraph.core.var import Var

class GraphNode:
    """Base Node For Nested CFG Representation of Program"""
    
    def __init__(self):
        self._next = [None]

    def setNext(self, index: int, n: 'GraphNode'):
        """Sets index'th successor node in CFG"""
        
        self._next[index] = n
        
    def getNext(self, index: int) -> 'GraphNode':
        """Get index'th successor node in CFG"""
        
        return self._next[index]

    def getReadVars(self) -> list:
        """Gets list of variables this CFG node may read from."""
        
        return []

    def getWriteVars(self) -> list:
        """Gets list of variables this CFG node may write to."""

        return []

class GraphVarWait(GraphNode):
    def __init__(self, readList: list, condVar: threading.Condition):
        super().__init__()
        self._readList = readList
        self._valMap = dict()
        self._condVar = condVar
        self._done = False

    def setDone(self):
        self._done = True
        
    def isDone(self) -> bool:
        return self._done
        
    def __setitem__(self, obj: Var, value):
        self._valMap[obj] = value

    def __getitem__(self, obj: Var):
        return self._valMap[obj]

    def getCondVar(self):
        return self._condVar
    
    def getReadVars(self) -> list:
        return self._readList

    async def execute(self, varMap: dict) -> dict:
        """Execute CondVar Wait."""

        for v in self._readList:
            self[v] = varMap[v]

        with self._condVar:
            # Set our done flag
            self.setDone()
            # Wake the waiters
            self._condVar.notify_all()
    
class GraphNested(GraphNode):
    """Nested CFG Node.  Used for control flow constructs such as
    If-Then-Else or a Loop."""
    
    def __init__(self, _start: GraphNode):
        super().__init__()
        self._start = _start
        self._readVars = None
        self._writeVars = None

    def getStart(self) -> GraphNode:
        """Gets first operation from child CFG."""
        
        return self._start

    def getReadVars(self) -> list:
        return self._readVars
        
    def getWriteVars(self) -> list:
        return self._writeVars
    
    def setReadVars(self, readVars: list):
        self._readVars = readVars
        
    def setWriteVars(self, writeVars: list):
        self._writeVars = writeVars

class GraphCall(GraphNested):
    """Calls another graph."""

    def __init__(self):
        """inMap maps caller parameters Vars to the callee Vars that provide the value.

        outMap maps caller return Vars to the callee Vars that should be assigned."""
        
        super().__init__(None)
        self._call = None
        self._inMap = None
        self._outMap = None

    def getStart(self) -> GraphNode:
        return self._call.getStart()
        
    def setCallee(self, call: GraphNode):
        self._call = call

    def setInMap(self, inMap: dict):
        self._inMap = inMap

    def setOutMap(self, outMap: dict):
        self._outMap = outMap
        
    def getReadVars(self) -> list:
        varList = list()
        for v in self._call.readVars():
            newvar = v
            if self._inMap != None:
                if v in self._inMap:
                    newvar = self._inMap[v]
                
            if not newvar in varList:
                varList.append(newvar)
        return varList
        
    def getWriteVars(self) -> list:
        varList = list()
        for v in self._call.writeVars():
            newvar = v
            if self._outMap != None:
                if v in self._outMap:
                    newvar = self._outMap[v]
                
            if not newvar in varList:
                varList.append(newvar)
        return varList
        
        
class GraphLLMAgent(GraphNode):
    """Run some action.  This is a LLM Agent."""
    
    def __init__(self, outVar: Var,  conversation: Var, model: LLMModel, msg: MsgSeq, formatFunc, kw: dict, pos:list):
        super().__init__()
        self.outVar = outVar
        self.conversation = conversation
        self.model = model
        self.msg = msg
        self.formatFunc = formatFunc
        self.kw = kw if kw != None else {}
        self.pos = pos if pos != None else []
        
    def getReadVars(self) -> list:
        l = list(self.kw.values())
        l.extend(self.pos)
        if self.conversation is not None:
            l.append(self.conversation)
        if self.msg != None:
            for var in self.msg.getVars():
                if not var in l:
                    l.append(var)
        return l
        
    def getWriteVars(self) -> list:
        return [self.outVar]

    async def execute(self, varMap: dict) -> dict:
        """Execute LLM Agent.  varMap maps Vars to the values that
        should be used for the execution."""

        if self.msg != None:
            output = self.msg.exec(varMap)
        else:
            posList = list()
            for var in self.pos:
                posList.append(varMap[var])

            inMap = dict()
            # First, compose dictionary for inVars (str -> Var) and varMap
            # (Var -> Value) to generate inMap (str -> Value)
            for name, var in self.kw:
                inMap[name] = varMap[var]

            # Next, actually call the formatFunc to generate the prompt
            output = await self.formatFunc(*posList, **inMap)
        print(output)
        # Call the model
        model = self.model
        if model is None:
            from agentgraph.exec.scheduler import getCurrentScheduler
            model = getCurrentScheduler().getDefaultModel()
        
        outStr = await model.sendData(output)
        # Update conversation
        if self.conversation is not None:
            varMap[self.conversation].push(outStr)
        
        # Put result in output map
        outMap = dict()
        outMap[self.outVar] = outStr
        
        return outMap
        
class GraphPythonAgent(GraphNested):
    """Run some action.  This is a Python Agent."""
    
    def __init__(self, pythonFunc, pos: list, kw: dict, out: list):
        """inVars is a map from names to Var objects that provide
        values for those variables.  The python function will be
        passed a dict that maps these names to values.

        The python function is expected to return a dict that maps
        names to values.  The out mapping maps those names to the
        Variables whose values should be updated with the values
        returned by the Python function.
        """
        
        super().__init__(None)
        self.pythonFunc = pythonFunc
        self.pos = pos if pos != None else []
        self.kw = kw if kw != None else {}
        self.out = out if out != None else []

    def getReadVars(self) -> list:
        return list(self.kw.values()) + self.pos
        
    def getWriteVars(self) -> list:
        return self.out

    def execute(self, scheduler: 'agentgraph.exec.scheduler.Scheduler', varMap: dict) -> dict:
        """Execute Python Agent.  Takes as input the scheduler object
        for the python agent task (in case it generates child tasks)
        and the varMap which maps Vars to the values to be used when
        executing the python agent."""

        # Build positional variables
        posList = list()
        for var in self.pos:
            posList.append(varMap[var])
        
        # First, compose dictionary for inVars (str -> Var) and varMap
        # (Var -> Value) to generate inMap (str -> Value)
        
        inMap = dict()
        for name, var in self.kw:
            inMap[name] = varMap[var]

        # Next, actually call the formatFunc to generate the prompt
        retval = self.pythonFunc(scheduler, *posList, **inMap)

        # Construct outMap (Var -> Object) from outVars (name -> Var)
        # and omap (name -> Value)
        
        outMap = dict()
        index = 0
        for var in self.out:
                outMap[var] = retval[index]
                index += 1
                
        return outMap
    
class GraphNodeNop(GraphNode):
    """Create a Nop Node."""
    
    def __init__(self):
        super().__init__()

class GraphNodeBranch(GraphNode):
    """Conditional branch node."""
    
    def __init__(self, branchVar):
        super().__init__()
        self._next.append(None)
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

    def __or__(a: 'GraphPair', b: 'GraphPair') -> 'GraphPair':
        return createSequence([a, b])
    
def checkInVars(pos: list, kw: dict):
    mutSet = set()
    if kw is not None:
        for v, var in kw:
            if var.isMutable():
                mutSet.add(var)
    if pos is not None:
        for var in pos:
            if var.isMutable():
                mutSet.add(var)
    if kw is not None:
        for v, var in kw:
            if var.isMutable() and var.isRead() and var.getVar() in mutSet:
                raise RuntimeException(f"Snapshotted and mutable versions of {var.getVar().getName()} used by same task.")
    if pos is not None:
        for var in pos:
            if var.isMutable() and var.isRead() and var.getVar() in mutSet:
                raise RuntimeException(f"Snapshotted and mutable versions of {var.getVar().getName()} used by same task.")

        
class VarMap:
    def __init__(self):
        self._varMap = dict()
        self._nameToVar = dict()

    def _getVariable(self, name: str) -> Var:
        if not name in self._nameToVar:
            self._nameToVar[name] = Var(name)
        return self._nameToVar[name]

    def _getBoolVariable(self, name: str) -> Var:
        if not name in self._nameToVar:
            self._nameToVar[name] = BoolVar(name)
        return self._nameToVar[name]

    def _getMutVariable(self, name: str) -> Var:
        if not name in self._nameToVar:
            self._nameToVar[name] = MutVar(name)
        return self._nameToVar[name]
        
    def getVarMap(self) -> dict:
        return self._varMap
        
    def mapToConversation(self, name: str, val: Conversation = None) -> MutVar:
        var = self._getMutVariable(name)
        if val is None:
            val = Conversation()
        self._varMap[var] = val
        return var

    def mapToFileStore(self, name: str, val: FileStore = None) -> MutVar:
        var = self._getMutVariable(name)
        if val is None:
            val = FileStore()
        self._varMap[var] = val
        return var

    def mapToMutable(self, name: str, val: Mutable) -> MutVar:
        var = self._getMutVariable(name)
        self._varMap[var] = val
        return var
    
    def mapToBool(self, name: str, val: bool) -> BoolVar:
        var = self._getBoolVariable(name)
        self._varMap[var] = val
        return var

    def mapToInt(self, name: str, val: int) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var
    
    def mapToString(self, name: str, val: str) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var
    
def createLLMAgent(outVar: Var, conversation: Var = None, model: LLMModel = None, msg: MsgSeq = None, formatFunc = None, pos: list = None, kw: dict = None) -> GraphPair:
    """Creates a LLM agent task.

    Arguments:
    outVar --- a Variable that will have the value of the output of the LLM.
    conversation --- a Variable that will point to the conversation object for this LLM.
    msg --- a MsgSeq object that can be used to generate the input to the LLM. (default None)
    formatFunc --- a Python function that generates the input to the LLM. (default None)
    inVars --- a dict mapping from names to Vars for the input to the formatFunc Python function. (default None)
    model --- a Model object for performing the LLM call (default None).
    
    You must either provide a msg object or a formatFunc object (and not both).
    """

    assert msg is not None or formatFunc is not None, "Either msg or formatFunc must be specified."
    assert msg is None or formatFunc is None, "Cannot specify both msg and formatFunc."
        
    checkInVars(pos, kw)
    llmAgent = GraphLLMAgent(outVar, conversation, model, msg, formatFunc, pos, kw)
    return GraphPair(llmAgent, llmAgent)

def createPythonAgent(pythonFunc, pos: list = None, kw: dict = None, out: list = None) -> GraphPair:
    """Creates a Python agent task.
    
    Arguments:
    pythonFunc --- a Python function to be executed.
    inVars --- a dict mapping from names to Vars for the input to the pythonFunc Python function. (default None)
    out --- a dict mapping from names to Vars for the output of the pythonFunc Python function.  (default None)
    """
    
    checkInVars(pos, kw)
    pythonAgent = GraphPythonAgent(pythonFunc, pos, kw, out)
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
    branch.setNext(0, None)
    
    #Save variable read/write results
    graph.setReadVars(readSet)
    graph.setWriteVars(writeSet)
    
    return GraphPair(graph, graph)

def createIfElse(condvar: BoolVar, thenN: GraphPair, elseN: GraphPair) -> GraphPair:
    """This creates an if then else block."""
    
    # Analyze variable reads/writes
    readSetThen, writeSetThen = analyzeLinear(thenN.start, thenN.end)
    readSetElse, writeSetElse = analyzeLinear(elseN.start, elseN.end)
    branch = GraphNodeBranch(condvar)
    graph = GraphNested(branch)
    branch.setNext(0, elseN.start)
    branch.setNext(1, thenN.start)
    thenN.last.setNext(0, None)
    elseN.last.setNext(0, None)
        
    #Combine variable reads/writes
    readSetThen.update(readSetElse)
    writeSetThen.update(writeSetElse)
    readSetThen.add(condvar)

    #Save variable read/write results
    graph.setReadVars(readSetThen)
    graph.setWriteVars(writeSetThen)
    
    return GraphPair(graph, graph)

def createRunnable(pair: GraphPair) -> GraphNested:
    """Encapsulates a GraphPair to make it runnable"""
    readSet, writeSet = analyzeLinear(pair.start, pair.end)
    graph = GraphNested(pair.start)
    pair.end.setNext(0, None)
        
    graph.setReadVars(readSet)
    graph.setWriteVars(writeSet)
    return graph

def analyzeLinear(start: GraphNode, end: GraphNode) -> tuple[set, set]:
    """ This function analyzes reads/writes of linear chains"""
    
    node = start
    list = []
    while node != None:
        list.append(node)
        node = node.getNext(0)
        
    readSet = set()
    writeSet = set()
    for i in range(len(list) - 1, -1, -1):
        n = list[i]
        writeSet.update(n.getWriteVars())
        readSet.difference_update(n.getWriteVars())
        readSet.update(n.getReadVars())
        
    return (readSet, writeSet)
