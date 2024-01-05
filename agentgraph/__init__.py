from agentgraph.core.graph import VarMap, createLLMAgent, createPythonAgent, createSequence, createDoWhile, createIfElse, createRunnable
from agentgraph.core.llmmodel import LLMModel
from agentgraph.core.conversation import Conversation
from agentgraph.core.prompts import Prompts
from agentgraph.core.var import Var
from agentgraph.core.mutvar import MutVar
from agentgraph.core.boolvar import BoolVar

def getRootScheduler(eng: 'agentgraph.exec.engine.Engine' = None):
    """Creates a root scheduler."""
    
    from agentgraph.exec.scheduler import Scheduler, setCurrentTask, setCurrentScheduler
    from agentgraph.exec.engine import Engine
    
    if eng is None:
        eng = Engine()
    
    scheduler = Scheduler(None, None, eng)
    setCurrentTask(None)
    setCurrentScheduler(scheduler)
    return scheduler
