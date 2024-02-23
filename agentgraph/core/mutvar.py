from agentgraph.core.var import Var

class MutVar(Var):
    def __init__(self, name: str = None):
        super().__init__(name)

    def isMutable(self) -> bool:
        return True

class MutVarFactory:
    def __init__(self):
        pass

    def allocator(self) -> MutVar:
        return MutVar()
