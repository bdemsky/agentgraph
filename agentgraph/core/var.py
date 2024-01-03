from agentgraph.core.msgseq import MsgSeq

class Var(MsgSeq):
    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def getName(self) -> str:
        return self.name

    def isMutable(self) -> bool:
        return False

    def isRead(self) -> bool:
        return False

    def getVars(self) -> set:
        return { self }

    def exec(self, varsMap: dict):
        return varsMap[self]
