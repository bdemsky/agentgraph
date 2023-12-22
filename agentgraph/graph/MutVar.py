from agentgraph.graph.Var import Var

class MutVar(Var):
    def __init__(self, name: str):
        super().init(name)

    def isMutable(self) -> bool:
        return True
