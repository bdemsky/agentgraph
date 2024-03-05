from functools import wraps
import inspect
from typing import Callable
import re

class ArgMapFunc:
    def __init__(self, func: Callable, argMap: dict):
        self.func = func
        self.argMap = argMap
        # copy over function attributes
        wraps(func)(self)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

def withArgMap(argMap = {}):
    """declare a function with dependencies on agentgraph variables"""
    def inner(func):
        return ArgMapFunc(func, argMap)
    return inner

def funcToToolSig(func: Callable) -> dict:
    func_dict = {"name": func.__name__}
    sig = inspect.signature(func)
    params = sig.parameters
    ignore = set(func.argMap.keys()) if type(func) is ArgMapFunc else set()

    desc_dict = {}
    doc = func.__doc__
    if doc:
        descs = re.split(r"\n+\s*Arguments:", doc)
        func_dict["description"] = descs[0]
        # there are parameter descriptions
        if len(descs) > 1:
            matches = re.findall(r"\n+\s*(\w+) --- (.*)", descs[1])
            for param_name, param_desc in matches:
                assert param_name in params, "unknown parameter"
                desc_dict[param_name] = param_desc

    if params:
        properties = {}
        required = []
        for param_name in params:
            if param_name in ignore:
                continue
            if param_name in desc_dict:
                properties[param_name] = {"type": typeToJSONSchema(func.__annotations__[param_name]), "description": desc_dict[param_name]}

                param_obj = params[param_name]
                if param_obj.default is param_obj.empty:
                    required.append(param_name)

        func_dict["parameters"] =  {"type": "object", "properties": properties, "required": required}

    return {"type": "function", "function" : func_dict}

def typeToJSONSchema(ty: type) -> str:
    if ty is bool:
        return "boolean"
    if ty is str:
        return "string"
    if ty is int:
        return "integer"
    if ty is float:
        return "number"
    if ty is dict:
        return "object"
    if ty is list:
        return "array"

    raise TypeError("unsupported type")
