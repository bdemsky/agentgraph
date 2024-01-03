from agentgraph.core.graph import VarMap, createLLMAgent, createPythonAgent, createSequence, createDoWhile, createIfElse, createRunnable


def getRootScheduler(eng: 'agentgraph.exec.Engine.Engine' = None):
    """Creates a root scheduler."""
    
    from agentgraph.exec.Scheduler import Scheduler
    from agentgraph.exec.Engine import Engine
    
    if eng is None:
        eng = Engine()
    
    return Scheduler(None, None, eng)
