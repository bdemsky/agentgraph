from agentgraph.graph.Action import Action
from agentgraph.exec.LLMState import LLMState

class LLMAgent(Action):
    def __init__(self, model):
        self.model = model
        
    async def run(self, state: LLMState, inVars: dict) -> dict:
        pass
