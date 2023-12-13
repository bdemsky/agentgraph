from agentgraph.graph.Node import Node
from agentgraph.exec.LLMState import LLMState

class Agent(Node):
    def __init__(self):
        pass
        
    def process(self, state: LLMState, val: 'agentgraph.graph.Var') -> 'agentgraph.graph.Var':
        pass
