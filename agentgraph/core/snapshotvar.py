from agentgraph.core.var import Var

class SnapshotVar(Var):
    """Wrapper class for variables that will be snapshotted"""
    def __init__(self, var: Var):
        self.var = var

    def getVar(self) -> Var:
        return self.var

    def isMutable(self) -> bool:
        return True

    def isRead(self) -> bool:
        return True
