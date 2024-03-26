from agentgraph.core.jinjamanager import JinjaManager
from agentgraph.core.mutable import Mutable
from agentgraph.core.prompts import Prompt
from agentgraph.core.reflect import funcToToolSig, Closure
from agentgraph.core.var import Var
import agentgraph
from dataclasses import dataclass
import json
from inspect import ismethod
from typing import Callable, Optional, Union
    
class Tool:
    def __init__(self, handler: Optional[Callable]):
        self.handler = handler
        self.readset = set()
        self.refs = set()

        if ismethod(handler) and isinstance(handler.__self__, Mutable):
            self.refs.add(handler.__self__)

        if isinstance(handler, Closure):
            if ismethod(handler.func) and isinstance(handler.func.__self__, Mutable):
                self.refs.add(handler.func.__self__)
            for val in handler.argMap.values():
                if isinstance(val, Var):
                    if val.isMutable():
                        raise RuntimeError("tool cannot depend on mutvars")
                    self.readset.add(val)
                elif isinstance(val, Mutable):
                    self.refs.add(val)

    def exec(self, varsMap: dict) -> dict:
        assert False
        return dict()
        
    def getReadSet(self) -> set:
        return self.readset

    def getRefs(self) -> set:
        return self.refs

    def getHandler(self) -> Optional[Callable]:
        return self.handler

class ToolReflect(Tool):
    def __init__(self, func: Callable, createHandler: bool = True):
        """
        func should be a callable available for the LLM to call. The function and argument descriptions are extracted from the function docstring with the format:
            FUNC_DESCPITON
            Arguments:
            ARG1 --- ARG1_DESCRIPTION
            ARG2 --- ARG2_DESCRIPTION
            ...
        only arguments with descriptions are included in the request to LLM.
        """

        handler = func if createHandler else None
        super().__init__(handler)
        self.toolSig: dict = funcToToolSig(func)

    def exec(self, varsMap: dict) -> dict:
        return self.toolSig

class ToolPrompt(Tool):
    def __init__(self, prompt: Prompt, handler: Callable):
        super().__init__(handler)
        self.prompt = prompt

    def exec(self, varsMap: dict) -> dict:
        """Compute value of tool signature at runtime"""
        val = self.prompt.exec(varsMap)
        toolSig = json.loads(val)
        validateToolSig(toolSig)
        return toolSig

    def getReadSet(self) -> set:
        return super().getReadSet().union(self.prompt.getReadSet())

def validateToolSig(tool):
    assert type(tool) is dict, "tool must be a dictionary"
    assert "type" in tool, "missing type in tool"
    assert tool["type"] == "function", "currently only function is supported in tools"
    assert "function" in tool, "missing function in tool"

class ToolList(Mutable):
    def __init__(self, tools: list[Tool] = [], owner = None):
        super().__init__(owner)
        for tool in tools:
            self.takeToolOwnership(tool)
        self.tools = tools

    def takeToolOwnership(self, tool):
        for ref in tool.getRefs():
            ref.setOwningObject(self) 
 
    def exec(self, varsMap: dict) -> tuple[list[dict], dict[str, Callable]]:
        toolsParam = []
        handlers = {}
        for tool in self.tools:
            toolSig = tool.exec(varsMap)
            toolsParam.append(toolSig)
            handler = tool.getHandler()
            assert handler is not None
            handlers[toolSig["function"]["name"]] = handler 
        return toolsParam, handlers

    def getReadSet(self) -> set:
        readSet = set()
        for tool in self.tools:
            readSet |= tool.getReadSet()
        return readSet

    def append(self, tool: Tool):
        self.takeToolOwnership(tool)
        self.tools.append(tool)

    def pop(self, *args) -> Tool:
        return self.tools.pop(*args)

def toolsFromFunctions(funcs: list[Callable]):
    return ToolList(list(map(ToolReflect, funcs)))

def toolsFromPrompts(loader: 'agentgraph.core.prompts.Prompts', PromptMap: dict):
    return ToolList([ToolPrompt(loader.loadPrompt(k), handler=v) for k, v in PromptMap.items()])
