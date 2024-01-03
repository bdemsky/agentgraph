from agentgraph.core.var import Var

class MutVar(Var):
    def __init__(self, name: str):
        super().__init__(name)

    def isMutable(self) -> bool:
        return True
