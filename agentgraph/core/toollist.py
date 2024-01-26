from agentgraph.core.jinjamanager import JinjaManager
from agentgraph.core.reflect import funcToTool
import json
from typing import Callable

class ToolList:
    def __init__(self):
        pass

    def exec(self, varsMap: dict) -> list[dict]:
        pass

    def getVars(self) -> set:
        return set()

class ToolsReflect(ToolList):
    def __init__(self, funcs: list[Callable]):
        self.tools: list[dict] = list(map(funcToTool, funcs))

    def exec(self, varsMap: dict) -> list[dict]:
        return self.tools

class ToolsPrompt(ToolList):
    def __init__(self, toolLists: 'ToolLists', name: str, vars: set):
        super().__init__()
        self.toolLists = toolLists
        self.name = name
        self.vars = vars

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

def validate_tool(tool):
    assert type(tool) is dict, "tool must be a dictionary"
    assert "type" in tool, "missing type in tool"
    assert tool["type"] == "function", "curretnly only function is supported in tools"
    assert "function" in tool, "missing function in tool"

def validate_tools(tools):
    assert type(tools) is list, "tools must be a list"
    for tool in tools:
        validate_tool(tool)

class ToolLists(JinjaManager):
    def loadToolList(self, tools_name: str, vars: set = None) -> ToolsPrompt:
        if vars == None:
            vars = set()
        return ToolsPrompt(self, tools_name, vars)    
