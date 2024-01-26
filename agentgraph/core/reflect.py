import inspect
from typing import Callable
import re

def funcToTool(func: Callable) -> dict:
    func_dict = {"name": func.__name__}
    sig = inspect.signature(func)
    params = sig.parameters

    properties = {}
    if params:
        required = []
        for param_name in params:
            properties[param_name] = {"type": typeToJSONSchema(func.__annotations__[param_name])} 
            param_obj = params[param_name]
            if param_obj.default is param_obj.empty:
                required.append(param_name)
        func_dict["parameters"] =  {"type": "object", "properties": properties, "required": required}

    doc = func.__doc__
    if doc:
        descs = re.split(r"\n+\s*Arguments:", doc)
        func_dict["description"] = descs[0]
        # there are parameter descriptions
        if len(descs) > 1:            
            matches = re.findall(r"\n+\s*(\w+) --- (.*)", descs[1])
            for param_name, param_desc in matches:
                assert param_name in properties, "description for unknown parameter"
                properties[param_name]["description"] = param_desc 

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
