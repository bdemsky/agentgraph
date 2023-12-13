from agentgraph.exec.LLMState import LLMState

class Node:
    def __init__(self):
        pass

    def process(self, state: LLMState, val: 'agentgraph.graph.Var') -> 'agentgraph.graph.Var':
        """Executes the current graph node.
        """
        raise Exception("Called process on Node class.")

    
