import agentgraph
from agentgraph.core.graph import VarMap
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.conversation import Conversation
from agentgraph.core.prompts import Prompts
from agentgraph.core.tools import toolsFromFunctions, toolsFromPrompts, ToolReflect, ToolPrompt, ToolList
from agentgraph.core.reflect import Closure, asClosure
from agentgraph.core.var import Var
from agentgraph.core.varset import VarSet
from agentgraph.core.vardict import VarDict
from agentgraph.data.filestore import FileStore
from typing import Optional

def getRootScheduler(model, eng: Optional['agentgraph.exec.engine.Engine'] = None):
    """Creates a root scheduler."""
    
    from agentgraph.exec.scheduler import Scheduler, setCurrentTask, setCurrentScheduler
    from agentgraph.exec.engine import Engine
    
    if eng is None:
        eng = Engine()
    
    scheduler = Scheduler(model, None, None, eng)
    setCurrentTask(None)
    setCurrentScheduler(scheduler)
    return scheduler

