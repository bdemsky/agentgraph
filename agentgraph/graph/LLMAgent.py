import asyncio
from agentgraph.graph.Action import Action
from agentgraph.graph.LLMModel import LLMModel
from agentgraph.exec.LLMState import LLMState

class LLMAgent(Action):
    def __init__(self, model: LLMModel):
        self.model = model
        
    async def run(self, state: LLMState, inVars: dict) -> dict:
        
        await self.model.sendData(message)
