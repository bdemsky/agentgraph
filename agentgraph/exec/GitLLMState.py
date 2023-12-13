from agentgraph.exec.LLMState import LLMState
from agentgraph.exec.Engine import Engine

class GitLLMState(LLMState):
    def __init__(self, _engine: Engine):
        super().__init__(_engine)
