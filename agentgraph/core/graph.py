import asyncio
import json
import traceback
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Union

from agentgraph.core.conversation import Conversation
from agentgraph.data.filestore import FileStore
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.msgseq import MsgSeq
from agentgraph.core.mutable import Mutable
from agentgraph.core.reflect import Closure
from agentgraph.core.tools import ToolList
from agentgraph.core.var import Var
from agentgraph.core.vardict import VarDict
from agentgraph.core.varset import VarSet
import agentgraph.config

class GraphNode:
    """Base Node For Nested CFG Representation of Program"""
    
    def __init__(self):
        self._next = [None]

    def set_next(self, index: int, n: Optional['GraphNode']):
        """Sets index'th successor node in CFG"""
        
        self._next[index] = n
        
    def get_next(self, index: int) -> Optional['GraphNode']:
        """Get index'th successor node in CFG"""
        
        return self._next[index]

    def _get_read_set(self) -> list:
        """Gets list of variables this CFG node may read from."""
        
        return []

    def get_write_vars(self) -> list:
        """Gets list of variables this CFG node may write to."""

        return []

class GraphVarWait(GraphNode):
    def __init__(self, readList: list, condVar: threading.Condition):
        super().__init__()
        self._readList = readList
        self._valMap : Dict[Var, Any] = dict()
        self._condVar = condVar
        self._done = False

    def set_done(self):
        self._done = True
        
    def is_done(self) -> bool:
        return self._done
        
    def __setitem__(self, obj: Var, value):
        self._valMap[obj] = value

    def __getitem__(self, obj: Var):
        return self._valMap[obj]

    def get_cond_var(self):
        return self._condVar
    
    def _get_read_set(self) -> list:
        return self._readList

    async def execute(self, varMap: dict) -> dict:
        """Execute CondVar Wait."""

        for v in self._readList:
            self[v] = varMap[v]

        with self._condVar:
            # Set our done flag
            self.set_done()
            # Wake the waiters
            self._condVar.notify_all()

        return dict()
            
class GraphNested(GraphNode):
    """Nested CFG Node."""
    
    def __init__(self, _start: Optional[GraphNode]):
        super().__init__()
        self._start = _start
        self._readVars : List[Any] = list()
        self._writeVars : List[Any] = list()

    def getStart(self) -> Optional[GraphNode]:
        """Gets first operation from child CFG."""
        
        return self._start

    def _get_read_set(self) -> list:
        return self._readVars
        
    def get_write_vars(self) -> list:
        return self._writeVars
    
    def set_read_vars(self, readVars: list):
        self._readVars = readVars
        
    def set_write_vars(self, writeVars: list):
        self._writeVars = writeVars

class GraphLLMAgent(GraphNode):
    """Run some action.  This is a LLM Agent."""
    
    def __init__(self, outVar: Var, conversation: Union[Var, Conversation, None], model: Optional[LLMModel], msg: Optional[MsgSeq], formatFunc, callVar: Optional[Var], tools: Optional[ToolList], pos: Optional[list], kw: Optional[dict]):
        super().__init__()
        self.outVar = outVar
        self.callVar = callVar
        self.conversation = conversation
        self.model = model
        self.msg = msg
        self.formatFunc = formatFunc
        self.tools = tools
        self.pos = pos if pos is not None else []
        self.kw = kw if kw is not None else {}
        
    def _get_read_set(self) -> list:
        l = list(self.kw.values())
        l.extend(self.pos)
        if self.conversation is not None:
            l.append(self.conversation)
        if self.msg is not None:
            for var in self.msg._get_read_set():
                if not var in l:
                    l.append(var)
        if self.tools is not None:
            l.append(self.tools)
            for var in self.tools._get_read_set():
                if not var in l:
                    l.append(var)
        return l
        
    def get_write_vars(self) -> list:
        return [self.outVar, self.callVar]

    async def execute(self, varMap: dict) -> dict:
        """Execute LLM Agent.  varMap maps Vars to the values that
        should be used for the execution."""

        if self.msg is not None:
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

        if self.tools is not None:
            try:
                toolsParam, handlers = self.tools.exec(varMap)
            except Exception as e:
                print('Error', e)
                print(traceback.format_exc())
                return dict()
        else:
            toolsParam, handlers = None, None

        model = self.model
        if model is None:
            from agentgraph.exec.scheduler import _get_current_scheduler
            model = _get_current_scheduler().get_default_model()
        
        message = await model.send_data(inConv, toolsParam)
        content = message["content"] if "content" in message else None
        toolCalls = message["tool_calls"] if "tool_calls" in message else None

        outStr = content if content is not None else json.dumps(toolCalls)
        
        # Update conversation with tool calls
        if self.conversation is not None:
            # Get conversation object
            if isinstance(self.conversation, agentgraph.core.var.Var):
                actConv = varMap[self.conversation]
            else:
                actConv = self.conversation

            #Make the output conversation match the full discussion
            actConv.load_conv(inConv)
            actConv.push(outStr)

        # Put result in output map
        outMap = dict()
        outMap[self.outVar] = content

        if toolCalls is not None and handlers is not None:
            handle_calls(toolCalls, handlers, varMap)

            # Update conversation with tool call results
            if self.conversation is not None:
                for call in toolCalls:
                    if "return" in call:
                        toolMsg = json.dumps({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": call["return"]})
                        actConv.push(toolMsg)

        if self.callVar is not None:
            outMap[self.callVar] = toolCalls
        
        return outMap

def handle_calls(calls: list, handlers: dict, varMap: dict):
   for call in calls:
       func = call['function']
       try:
           handler = handlers[func['name']]
           args = json.loads(func['arguments'])
       except Exception as e:
           call["exception"] = e
       else:
           if type(handler) is Closure:
               for arg, item in handler.argMap.items():
                    args[arg] = varMap[item] if isinstance(item, Var) else item 
           if handler is not None:
               call["return"] = handler(**args)

class GraphPythonAgent(GraphNested):
    """Run some action.  This is a Python Agent."""
    
    def __init__(self, pythonFunc, pos: Optional[list], kw: Optional[dict], out: Optional[list]):
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
        self.pos = pos if pos is not None else []
        self.kw = kw if kw is not None else {}
        self.out = out if out is not None else []

    def _get_read_set(self) -> list:
        return list(self.kw.values()) + self.pos
        
    def get_write_vars(self) -> list:
        return self.out

    def execute(self, scheduler: 'agentgraph.exec.scheduler.Scheduler', varMap: dict) -> dict:
        """Execute Python Agent.  Takes as input the scheduler object
        for the python agent task (in case it generates child tasks)
        and the varMap which maps Vars to the values to be used when
        executing the python agent."""

        # Build positional variables
        posList : List[Any] = list()
        for o in self.pos:
            if isinstance(o, agentgraph.core.vardict.VarDict):
                newdict = dict()
                for key, value in o.items():
                    if isinstance(value, agentgraph.core.var.Var):
                        newdict[key] = varMap[value]
                    elif isinstance(value, agentgraph.core.mutable.ReadOnly):
                        m = value.get_mutable()
                        mutable = varMap[m] if isinstance(m, agentgraph.core.var.Var) else m
                        proxy = mutable._get_read_only_proxy()
                        assert isinstance(proxy, agentgraph.core.mutable.ReadOnlyProxy), \
                            '_get_read_only_proxy() must return an instance of ReadOnlyProxy'
                        assert proxy._mutable == mutable, 'ReadOnlyProxy._mutable must be the original mutable'
                        newdict[key] = proxy
                    else:
                        newdict[key] = value

                posList.append(newdict)
            elif isinstance(o, agentgraph.core.varset.VarSet):
                news = set()
                for v in o:
                    if isinstance(v, agentgraph.core.var.Var):
                        news.add(varMap[v])
                    elif isinstance(v, agentgraph.core.mutable.ReadOnly):
                        m = v.get_mutable()
                        mutable = varMap[m] if isinstance(m, agentgraph.core.var.Var) else m
                        proxy = mutable._get_read_only_proxy()
                        assert isinstance(proxy, agentgraph.core.mutable.ReadOnlyProxy), \
                            '_get_read_only_proxy() must return an instance of ReadOnlyProxy'
                        assert proxy._mutable == mutable, 'ReadOnlyProxy._mutable must be the original mutable'
                        news.add(proxy)
                    else:
                        news.add(v)
                    
                posList.append(news)
            elif isinstance(o, agentgraph.core.var.Var):
                posList.append(varMap[o])
            elif isinstance(o, agentgraph.core.mutable.ReadOnly):
                m = o.get_mutable()
                mutable = varMap[m] if isinstance(m, agentgraph.core.var.Var) else m
                proxy = mutable._get_read_only_proxy()
                assert isinstance(proxy, agentgraph.core.mutable.ReadOnlyProxy), \
                    '_get_read_only_proxy() must return an instance of ReadOnlyProxy'
                assert proxy._mutable == mutable, 'ReadOnlyProxy._mutable must be the original mutable'
                posList.append(proxy)
            else:
                posList.append(o)
        
        # First, compose dictionary for inVars (str -> Var) and varMap
        # (Var -> Value) to generate inMap (str -> Value)
        
        inMap : Dict[str, Any] = dict()
        for name, o in self.kw:
            if isinstance(o, agentgraph.core.vardict.VarDict):
                newdict = dict()
                for key, value in o.items():
                    if isinstance(value, agentgraph.core.var.Var):
                        newdict[key] = varMap[value]
                    elif isinstance(value, agentgraph.core.mutable.ReadOnly):
                        m = value.get_mutable()
                        mutable = varMap[m] if isinstance(m, agentgraph.core.var.Var) else m
                        proxy = mutable._get_read_only_proxy()
                        assert isinstance(proxy, agentgraph.core.mutable.ReadOnlyProxy), \
                            '_get_read_only_proxy() must return an instance of ReadOnlyProxy'
                        assert proxy._mutable == mutable, 'ReadOnlyProxy._mutable must be the original mutable'
                        newdict[key] = proxy
                    else:
                        newdict[key] = value

                inMap[name] = newdict
            elif isinstance(o, agentgraph.core.varset.VarSet):
                news = set()
                for v in o:
                    if isinstance(v, agentgraph.core.var.Var):
                        news.add(varMap[v])
                    elif isinstance(v, agentgraph.core.mutable.ReadOnly):
                        m = v.get_mutable()
                        mutable = varMap[m] if isinstance(m, agentgraph.core.var.Var) else m
                        proxy = mutable._get_read_only_proxy()
                        assert isinstance(proxy, agentgraph.core.mutable.ReadOnlyProxy), \
                            '_get_read_only_proxy() must return an instance of ReadOnlyProxy'
                        assert proxy._mutable == mutable, 'ReadOnlyProxy._mutable must be the original mutable'
                        news.add(proxy)
                    else:
                        news.add(v)
                    
                inMap[name] = news
            elif isinstance(o, agentgraph.core.var.Var):
                inMap[name] = varMap[o]
            elif isinstance(o, agentgraph.core.mutable.ReadOnly):
                m = o.get_mutable()
                mutable = varMap[m] if isinstance(m, agentgraph.core.var.Var) else m
                proxy = mutable._get_read_only_proxy()
                assert isinstance(proxy, agentgraph.core.mutable.ReadOnlyProxy), \
                    '_get_read_only_proxy() must return an instance of ReadOnlyProxy'
                assert proxy._mutable == mutable, 'ReadOnlyProxy._mutable must be the original mutable'
                inMap[name] = proxy
            else:
                inMap[name] = o
                
        # Next, actually call the formatFunc to generate the prompt
        retval = self.pythonFunc(scheduler, *posList, **inMap)

        # Construct outMap (Var -> Object) from outVars (name -> Var)
        # and omap (name -> Value)
        outMap = dict()
        index = 0
        for var in self.out:
            val = retval[index]
            assert not isinstance(val, agentgraph.core.mutable.ReadOnlyProxy), \
                'Cannot return an instance of ReadOnlyProxy from a Python agent'
            if isinstance(val, Var):
                newval = scheduler.read_variable(val)
            elif isinstance(val, VarSet):
                newval = set()
                for v in val:
                    if isinstance(v, Var):
                        newval.add(scheduler.read_variable(v))
                    else:
                        newval.add(v)
            elif isinstance(val, VarDict):
                newval = dict()
                for k, v in val:
                    if isinstance(v, Var):
                        newval[k] = scheduler.read_variable(v)
                    else:
                        newval[k] = v
            else:
                newval = val

            outMap[var] = newval
            index += 1

        return outMap

class GraphPair:
    """Stores the beginning and end node of a sub graph"""
    
    def __init__(self, start: GraphNode, end: GraphNode):
        self.start = start
        self.end = end

    def __or__(a: 'GraphPair', b: 'GraphPair') -> 'GraphPair':
        return create_sequence([a, b])
    
class VarMap:
    def __init__(self):
        self._varMap = dict()

    def _getVariable(self, name: Optional[str]) -> Var:
        return Var(name)

    def get_var_map(self) -> dict:
        return self._varMap
        
    def map_to_conversation(self, name: Optional[str] = None, val: Optional[Conversation] = None) -> Var:
        var = self._getVariable(name)
        if val is None:
            val = Conversation()
        self._varMap[var] = val
        return var

    def map_to_filestore(self, name: Optional[str] = None, val: Optional[FileStore] = None) -> Var:
        var = self._getVariable(name)
        if val is None:
            val = FileStore()
        self._varMap[var] = val
        return var

    def map_to_toollist(self, name: Optional[str] = None, val: Optional[ToolList] = None) -> Var:
        var = self._getVariable(name)
        if val is None:
            val = ToolList()
        self._varMap[var] = val
        return var

    def map_to_mutable(self, name: Optional[str] = None, val: Optional[Mutable] = None) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var
    
    def map_to_bool(self, name: Optional[str] = None, val: bool = False) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var

    def map_to_none(self, name: Optional[str] = None) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = None
        return var

    def map_to_int(self, name: Optional[str] = None, val: int = 0) -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var

    def map_to_str(self, name: Optional[str] = None, val: str = "") -> Var:
        var = self._getVariable(name)
        self._varMap[var] = val
        return var
    
def create_llm_agent(outVar: Var, msg: Optional[MsgSeq] = None, conversation: Union[Conversation, Var, None] = None, callVar: Optional[Var] = None, tools: Optional[ToolList] = None, formatFunc = None, pos: Optional[list] = None, kw: Optional[dict] = None, model: Optional[LLMModel] = None) -> GraphPair:
    """Creates a LLM agent task.

    Arguments:
    outVar --- a Variable that will have the value of the output of the LLM.
    msg --- a MsgSeq object that can be used to generate the input to the LLM. (default None)
    conversation --- a Variable that will point to the conversation object for this LLM.
    model --- a Model object for performing the LLM call (default None)
    callVar --- a Variable that will have the list of calls made by the LLM, if there is any. If a call has arguments that cannot be parsed as json, or if the called tool can't be found in the tools passed in, an exception is stored in the call with the key "exception". Otherwise if the called tool has a handler, the handler is called and the result is stored in the call with the key "return".  
    tools --- a ToolList object used to generate the tools parameter to the LLM.
    inVars --- a dict mapping from names to Vars for the input to the formatFunc Python function. (default None)
    formatFunc --- a Python function that generates the input to the LLM. (default None)
    
    You must either provide a msg object or a formatFunc object (and not both).
    """

    assert msg is not None or formatFunc is not None, "Either msg or formatFunc must be specified."
    assert msg is None or formatFunc is None, "Cannot specify both msg and formatFunc."

    llmAgent = GraphLLMAgent(outVar, conversation, model, msg, formatFunc, callVar, tools, pos, kw)
    return GraphPair(llmAgent, llmAgent)

def create_python_agent(pythonFunc, pos: Optional[list] = None, kw: Optional[dict] = None, out: Optional[list] = None) -> GraphPair:
    """Creates a Python agent task.
    
    Arguments:
    pythonFunc --- a Python function to be executed.
    inVars --- a dict mapping from names to Vars for the input to the pythonFunc Python function. (default None)
    out --- a dict mapping from names to Vars for the output of the pythonFunc Python function.  (default None)
    """

    pythonAgent = GraphPythonAgent(pythonFunc, pos, kw, out)
    return GraphPair(pythonAgent, pythonAgent)

def create_sequence(list) -> GraphPair:
    """This creates a sequency of GraphNodes"""

    start = list[0].start
    last = list[0].end
    for l in list[1:]:
        last.set_next(0, l.start)
        last = l.end
    return GraphPair(start, last)

def create_runnable(pair: GraphPair) -> GraphNested:
    """Encapsulates a GraphPair to make it runnable"""
    readSet, writeSet = analyze_linear(pair.start, pair.end)
    graph = GraphNested(pair.start)
    pair.end.set_next(0, None)

    graph.set_read_vars(readSet)
    graph.set_write_vars(writeSet)
    return graph

def analyze_linear(start: GraphNode, end: GraphNode) -> tuple[list, list]:
    """ This function analyzes reads/writes of linear chains"""

    node : Optional[GraphNode] = start
    mylist = []
    while node is not None:
        mylist.append(node)
        node = node.get_next(0)

    readSet: Set[Any] = set()
    writeSet: Set[Any] = set()
    for i in range(len(mylist) - 1, -1, -1):
        n = mylist[i]
        writeSet.update(n.get_write_vars())
        readSet.difference_update(n.get_write_vars())
        readSet.update(n._get_read_set())

    return list(readSet), list(writeSet)
