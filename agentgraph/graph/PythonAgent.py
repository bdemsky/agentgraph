from agentgraph.graph.Action import Action
from agentgraph.exec.LLMState import LLMState

class PythonAgent(Action):
    def __init__(self, func):
        self.func = func

    async def run(self, state: LLMState, inVars: dict) -> dict:
        return await self.func(state, inVars)
