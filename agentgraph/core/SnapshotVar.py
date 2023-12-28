from agentgraph.core.Var import Var
from agentgraph.core.MutVar import MutVar

class SnapshotVar(Var):
    """Wrapper class for variables that will be snapshotted"""
    def __init__(self, var: MutVar):
        self.var = var

    def getVar() -> MutVar:
        return self.var

    def isMutable() -> bool:
        return True

    def isRead() -> bool:
        return True
