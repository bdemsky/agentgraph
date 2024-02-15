from agentgraph.core.jinjamanager import JinjaManager
from agentgraph.core.reflect import funcToToolSig, ArgMapFunc
from dataclasses import dataclass
import json
from typing import Callable, Union


class Tool:
    def __init__(self):
        pass

    def exec(self, varsMap: dict) -> list[dict]:
        pass

    def getVars(self) -> set:
        return set()

    def getHandler(self) -> callable:
        return None

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
        super().__init__()
        self.vars = set()
        if type(func) is ArgMapFunc:
            self.vars.update(list(func.argMap.values()))
        self.toolSig: dict = funcToToolSig(func)
        self.handler = func if createHandler else None

    def exec(self, varsMap: dict) -> dict:
        return self.toolSig

    def getHandler(self) -> dict:
        return self.handler    

    def getVars(self) -> set:
        return self.vars

class ToolTemplate(Tool):
    def __init__(self, toolloader: 'ToolLoader', name: str, handler: Callable, vars: set):
        super().__init__()
        self.toolloader = toolloader
        self.name = name
        self.vars = vars
        if type(handler) is ArgMapFunc:
            self.vars.update(list(handler.argMap.values()))
        self.handler = handler

    def exec(self, varsMap: dict) -> dict:
        """Compute value of tool signature at runtime"""
        data = dict()
        for var in varsMap:
            value = varsMap[var]
            data[var.getName()] = value
        val = self.toolloader.runTemplate(self.name, data)
        toolSig = json.loads(val)
        validateToolSig(toolSig)
        return toolSig

    def getVars(self) -> set:
        return self.vars

    def getHandler(self) -> dict:
        return self.handler

def validateToolSig(tool):
    assert type(tool) is dict, "tool must be a dictionary"
    assert "type" in tool, "missing type in tool"
    assert tool["type"] == "function", "currently only function is supported in tools"
    assert "function" in tool, "missing function in tool"

class ToolLoader(JinjaManager):
    def loadTool(self, tool_name: str, handler: Callable = None, vars: set = set()) -> ToolTemplate:
        """
        handlers should be a dictionary that maps the name of each tool to a callable that handles the tool call. 
        """
        return ToolTemplate(self, tool_name, handler, vars)  
