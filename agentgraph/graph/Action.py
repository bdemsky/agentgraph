import asyncio
from agentgraph.exec.LLMState import LLMState

class Action:
    """Base class for actions."""
    def __init__(self):
        pass

    def run(self, state: LLMState, inVars: dict) -> dict:
        pass
