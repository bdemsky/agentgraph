import asyncio
import json
import traceback
import threading
from typing import Callable

from agentgraph.core.boolvar import BoolVar
from agentgraph.core.conversation import Conversation
from agentgraph.data.filestore import FileStore
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.msgseq import MsgSeq
from agentgraph.core.mutable import Mutable
from agentgraph.core.mutvar import MutVar
from agentgraph.core.reflect import ArgMapFunc
from agentgraph.core.tools import Tool
from agentgraph.core.var import Var
import agentgraph.config

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

    def getReadSet(self) -> list:
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
    
    def getReadSet(self) -> list:
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

        return dict()
            
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

    def getReadSet(self) -> list:
        return self._readVars
        
    def getWriteVars(self) -> list:
        return self._writeVars
    
    def setReadVars(self, readVars: list):
        self._readVars = readVars
        
    def setWriteVars(self, writeVars: list):
        self._writeVars = writeVars

class GraphLLMAgent(GraphNode):
    """Run some action.  This is a LLM Agent."""
    
    def __init__(self, outVar: Var, callVar: Var, conversation: Var, model: LLMModel, msg: MsgSeq, formatFunc, tools: list[Tool], pos: list, kw: dict):
        super().__init__()
        self.outVar = outVar
        self.callVar = callVar
        self.conversation = conversation
        self.model = model
        self.msg = msg
        self.formatFunc = formatFunc
        self.tools = tools
        self.toolHandlers = toolHandlers
        self.pos = pos if pos != None else []
        self.kw = kw if kw != None else {}
        
    def getReadSet(self) -> list:
        l = list(self.kw.values())
        l.extend(self.pos)
        if self.conversation is not None:
            l.append(self.conversation)
        if self.msg != None:
            for var in self.msg.getVars():
                if not var in l:
                    l.append(var)
        if self.tools != None:
            for tool in self.tools:
                for var in tool.getVars():
                    if not var in l:
                        l.append(var)
        return l
        
    def getWriteVars(self) -> list:
        return [self.outVar, self.callVar]

    async def execute(self, varMap: dict) -> dict:
        """Execute LLM Agent.  varMap maps Vars to the values that
        should be used for the execution."""

        if self.msg != None:
            try:
                inConv = self.msg.exec(varMap)
            except Exception as e:
                print('Error', e)
                print(traceback.format_exc())
                return dict()
        else:
            posList = list()
            for o in self.pos:
                if isinstance(o, agentgraph.core.var.Var):
                    posList.append(varMap[o])
                else:
                    posList.append(o)

            inMap = dict()
            # First, compose dictionary for inVars (str -> Var) and varMap
            # (Var -> Value) to generate inMap (str -> Value)
            for name, var in self.kw:
                if isinstance(o, agentgraph.core.var.Var):
                    inMap[name] = varMap[o]
                else:
                    inMap[name] = o

            # Next, actually call the formatFunc to generate the prompt
            inConv = await self.formatFunc(*posList, **inMap)
        if agentgraph.config.VERBOSE > 0:
            print("MODEL Request:\n", inConv)
        # Call the model

        if self.tools != None:
            try:
                toolsParam = []
                handlers = {}
                for tool in self.tools:
                    toolSig = tool.exec(varMap)
                    toolsParam.append(toolSig)
                    handlers[toolSig["function"]["name"]] = tool.getHandler() 
            except Exception as e:
                print('Error', e)
                print(traceback.format_exc())
                return dict()
        else:
            toolsParam = None
            handlers = None

        model = self.model
        if model is None:
            from agentgraph.exec.scheduler import getCurrentScheduler
            model = getCurrentScheduler().getDefaultModel()
        
        message = await model.sendData(output, toolsParam)
        content = message["content"] if "content" in message else None
        toolCalls = message["tool_calls"] if "tool_calls" in message else None

        outStr = content if content is not None else json.dumps(tool_calls)
        
        # Update conversation with tool calls
        if self.conversation is not None:
            # Get conversation object
            if isinstance(self.conversation, agentgraph.core.var.Var):
                actConv = varMap[self.conversation]
            else:
                actConv = self.conversation

            #Make the output conversation match the full discussion
            actConv.loadConv(inConv)
            actConv.push(outStr)

=======
            outStr = content if content is not None else json.dumps(toolCalls)
            varMap[self.conversation].push(outStr)
        
>>>>>>> 96195ca (refactor toollist into list of tool objects)
        # Put result in output map
        outMap = dict()
        outMap[self.outVar] = content

        callResults = None
        if toolCalls is not None and handlers is not None:
            callResults = handleCalls(toolCalls, handlers, varMap)

            # Update conversation with tool call results
            if self.conversation is not None:
                for call in callResults:
                    if "return" in call:
                        toolMsg = json.dumps({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": call["return"]})
                        varMap[self.conversation].push(toolMsg)

        if self.callVar is not None:
            outMap[self.callVar] = callResults if callResults is not None else toolCalls
        
        return outMap

def handleCalls(calls: list, handlers: dict, varMap: dict) -> list:
   for call in calls:
       func = call['function']
       try:
           handler = handlers[func['name']]
           args = json.loads(func['arguments'])
       except Exception as e:
           call["exception"] = e
       else:
           if type(handler) is ArgMapFunc: 
               for arg, var in handler.argMap.items():
                    args[arg] = varMap[var]
           if handler is not None:
               call["return"] = handler(**args)
   return calls

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

    def getReadSet(self) -> list:
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
        for o in self.pos:
            if isinstance(o, agentgraph.core.var.Var):
                posList.append(varMap[o])
            else:
                posList.append(o)
        
        # First, compose dictionary for inVars (str -> Var) and varMap
        # (Var -> Value) to generate inMap (str -> Value)
        
        inMap = dict()
        for name, o in self.kw:
            if isinstance(o, agentgraph.core.var.Var):
                inMap[name] = varMap[o]
            else:
                inMap[name] = o
                
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

    def getReadSet(self) -> list:
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
            if isinstance(var, agentgraph.core.var.Var) and var.isMutable():
                mutSet.add(var)
    if pos is not None:
        for var in pos:
            if isinstance(var, agentgraph.core.var.Var) and var.isMutable():
                mutSet.add(var)
    if kw is not None:
        for v, var in kw:
            if isinstance(var, agentgraph.core.var.Var) and var.isMutable() and var.isRead() and var.getVar() in mutSet:
                raise RuntimeError(f"Snapshotted and mutable versions of {var.getVar().getName()} used by same task.")
    if pos is not None:
        for var in pos:
            if isinstance(var, agentgraph.core.var.Var) and var.isMutable() and var.isRead() and var.getVar() in mutSet:
                raise RuntimeError(f"Snapshotted and mutable versions of {var.getVar().getName()} used by same task.")

        
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

    def _getMutVariable(self, name: str) -> MutVar:
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

    def mapToNone(self, name: str) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = None
        return var

    def mapToInt(self, name: str, val: int) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var
    
    def mapToString(self, name: str, val: str) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var
    
def createLLMAgent(outVar: Var, callVar: Var = None, conversation: Var = None, model: LLMModel = None, msg: MsgSeq = None, formatFunc = None, tools: list[Tool] = None, toolHandlers: dict = None, pos: list = None, kw: dict = None) -> GraphPair:
    """Creates a LLM agent task.

    Arguments:
    outVar --- a Variable that will have the value of the output of the LLM.
    callVar --- a Variable that will have the list of calls made by the LLM, if there is any. If a call has arguments that cannot be parsed as json, or if the called tool can't be found in the tools passed in, an exception is stored in the call with the key "exception". Otherwise if the called tool has a handler, the handler is called and the result is stored in the call with the key "return".  
    conversation --- a Variable that will point to the conversation object for this LLM.
    msg --- a MsgSeq object that can be used to generate the input to the LLM. (default None)
    formatFunc --- a Python function that generates the input to the LLM. (default None)
    tools --- a list of Tool objects that can be used to generate the tools parameter to the LLM.
    inVars --- a dict mapping from names to Vars for the input to the formatFunc Python function. (default None)
    model --- a Model object for performing the LLM call (default None)

    You must either provide a msg object or a formatFunc object (and not both).
    """

    assert msg is not None or formatFunc is not None, "Either msg or formatFunc must be specified."
    assert msg is None or formatFunc is None, "Cannot specify both msg and formatFunc."
        
    checkInVars(pos, kw)
    llmAgent = GraphLLMAgent(outVar, callVar, conversation, model, msg, formatFunc, tools, toolHandlers, pos, kw)
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
        readSet.update(n.getReadSet())
        
    return (readSet, writeSet)
