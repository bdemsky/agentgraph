from agentgraph.core.jinjamanager import JinjaManager
from agentgraph.core.reflect import funcToTool
import json
from typing import Callable, Union

class ToolList:
    def __init__(self):
        pass

    def exec(self, varsMap: dict) -> list[dict]:
        pass

    def getVars(self) -> set:
        return set()

    def getHandlers(self) -> dict:
        return {}

class ToolsReflect(ToolList):
    def __init__(self, funcs: list[Callable]):
        """
        funcs should be a list of functions available for the LLM to call. The function and arguments descriptions are extracted from function docstrings with the format
            FUNC_DESCPITON
            Arguments:
            ARG1 --- ARG1_DESCRIPTION
            ARG2 --- ARG2_DESCRIPTION
        ...
        """
        self.tools: list[dict] = list(map(funcToTool, funcs))
        self.handlers = {func.__name__: func for func in funcs}

    def exec(self, varsMap: dict) -> list[dict]:
        return self.tools

    def getHandlers(self) -> dict:
        return self.handlers

def validate_tool(tool):
    assert type(tool) is dict, "tool must be a dictionary"
    assert "type" in tool, "missing type in tool"
    assert tool["type"] == "function", "curretnly only function is supported in tools"
    assert "function" in tool, "missing function in tool"

def validate_tools(tools):
    assert type(tools) is list, "tools must be a list"
    for tool in tools:
        validate_tool(tool)

class ToolsPrompt(ToolList):
    def __init__(self, toolLists: 'ToolLists', name: str, vars: set, handlers: dict):
        super().__init__()
        self.toolLists = toolLists
        self.name = name
        self.vars = vars
        self.handlers = handlers

    def exec(self, varsMap: dict) -> list[dict]:
        """Compute value of tool list at runtime"""
        data = dict()
        for var in varsMap:
            value = varsMap[var]
            data[var.getName()] = value
        val = self.toolLists.runTemplate(self.name, data)
        tools = json.loads(val)
        if type(tools) is not list:
            tools = [tools]
        validate_tools(tools)
        return tools

    def getVars(self) -> set:
        return self.vars

    def getHandlers(self) -> dict:
        return self.handlers

class ToolLists(JinjaManager):
    def loadToolList(self, tools_name: str, vars: set = None, handlers: Union[dict, list] = None) -> ToolsPrompt:
        """
        handlers should be a dictionary that maps the name of each tool to a function that handles the tool call. 
        """
        if vars == None:
            vars = set()
        if type(handlers) is list:
            handlers = {handler.__name__: handler for handler in handlers} 
        return ToolsPrompt(self, tools_name, vars, handlers)  
