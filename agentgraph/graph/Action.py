import asyncio
from agentgraph.exec.LLMState import LLMState

class Action:
    """Base class for actions."""
    def __init__(self):
        pass

    async def run(self, state: LLMState, inVars: dict) -> dict:
        pass
