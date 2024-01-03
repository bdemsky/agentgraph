from agentgraph.core.graph import VarMap, createLLMAgent, createPythonAgent, createSequence, createDoWhile, createIfElse, createRunnable


def getRootScheduler(eng: 'agentgraph.exec.engine.Engine' = None):
    """Creates a root scheduler."""
    
    from agentgraph.exec.scheduler import Scheduler
    from agentgraph.exec.engine import Engine
    
    if eng is None:
        eng = Engine()
    
    return Scheduler(None, None, eng)
