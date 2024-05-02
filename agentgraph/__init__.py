import agentgraph
from agentgraph.core.graph import VarMap
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.conversation import Conversation
from agentgraph.core.prompts import Prompts
from agentgraph.core.tools import tools_from_functions, tools_from_prompts, ToolReflect, ToolPrompt, ToolList
from agentgraph.core.reflect import Closure, as_closure
from agentgraph.core.var import Var
from agentgraph.core.varset import VarSet
from agentgraph.core.vardict import VarDict
from agentgraph.data.filestore import FileStore
from agentgraph.data.process import Process
from typing import Optional

def get_root_scheduler(model, eng: Optional['agentgraph.exec.engine.Engine'] = None):
    """Creates a root scheduler."""
    
    from agentgraph.exec.scheduler import Scheduler, _set_current_task, _set_current_scheduler
    from agentgraph.exec.engine import Engine
    
    if eng is None:
        eng = Engine()
    
    scheduler = Scheduler(model, None, None, eng)
    _set_current_task(None)
    _set_current_scheduler(scheduler)
    return scheduler

