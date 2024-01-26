from agentgraph.core.graph import VarMap, createLLMAgent, createLLMAgentWithFuncs, createPythonAgent, createSequence, createDoWhile, createIfElse, createRunnable
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.conversation import Conversation
from agentgraph.core.prompts import Prompts
from agentgraph.core.toollist import ToolLists
from agentgraph.core.var import Var
from agentgraph.core.mutvar import MutVar
from agentgraph.core.boolvar import BoolVar
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
