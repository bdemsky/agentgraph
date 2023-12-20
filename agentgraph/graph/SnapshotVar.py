from agentgraph.graph.Var import Var
from agentgraph.graph.MutVar import MutVar

class SnapshotVar(Var):
    """Wrapper class for variables that will be snapshotted"""
    def __init__(self, var: MutVar):
        self.var = var

    def getVar() -> MutVar:
        return self.var
