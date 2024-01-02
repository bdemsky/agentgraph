from agentgraph.core.graph import graph, createLLMAgent, createPythonAgent, createSequence, createDoWhile, createIfElse, createRunnable

def getRootScheduler(eng: 'agentgraph.exec.Engine.Engine'):
    """Creates a root scheduler."""
    from agentgraph.exec.Scheduler import Scheduler
    
    return Scheduler(None, None, eng)
