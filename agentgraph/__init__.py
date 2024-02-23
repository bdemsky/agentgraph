from agentgraph.core.graph import VarMap
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.conversation import Conversation
from agentgraph.core.prompts import Prompts
from agentgraph.core.tools import ToolLoader, ToolReflect
from agentgraph.core.reflect import withArgMap
from agentgraph.core.var import VarFactory, Var
from agentgraph.core.varset import VarSet
from agentgraph.core.mutvar import MutVarFactory, MutVar
from agentgraph.data.filestore import FileStore

def getRootScheduler(model, eng: 'agentgraph.exec.engine.Engine' = None):
    """Creates a root scheduler."""
    
    from agentgraph.exec.scheduler import Scheduler, setCurrentTask, setCurrentScheduler
    from agentgraph.exec.engine import Engine
    
    if eng is None:
        eng = Engine()
    
    scheduler = Scheduler(model, None, None, eng)
    setCurrentTask(None)
    setCurrentScheduler(scheduler)
    return scheduler

VarType = VarFactory()
MutVarType = MutVarFactory()
