from agentgraph.core.var import Var

class BoolVar(Var):
    def __init__(self, name: str = None):
        super().__init__(name)
