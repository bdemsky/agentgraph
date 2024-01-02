from agentgraph.core.graph import graph, createLLMAgent, createPythonAgent, createSequence, createDoWhile, createIfElse, createRunnable
from agentgraph.exec.Engine import Engine
from agentgraph.exec.Scheduler import Scheduler

def getRootScheduler(eng: Engine):
    """Creates a root scheduler."""

    return Scheduler(None, None, eng)
