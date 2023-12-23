from agentgraph.graph.MsgSeq import MsgSeq

class Var(MsgSeq):
    def __init__(self, _name: str):
        super().__init()
        self.name = _name

    def getName(self) -> str:
        return self.name

    def isMutable(self) -> bool:
        return False

    def isRead(self) -> bool:
        return False

    def getVars(self) -> set:
        return { self }
