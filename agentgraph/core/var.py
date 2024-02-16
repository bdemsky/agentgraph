from agentgraph.core.msgseq import MsgSeq

varNameCount = 0

class Var(MsgSeq):
    def __init__(self, name: str = None):
        super().__init__()
        if name is None:
            global varNameCount
            name = f"VAR{varNameCount}"
            varNameCount += 1
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
        lookup = varsMap[self]
        if isinstance(lookup, str):
            return lookup
        else:
            return lookup.exec(varsMap)

    def getValue(self):
        """Method that will return the value the variable is assigned
        by the most recent dispatched task that writes to it.
        """
        
        from agentgraph.exec.scheduler import getCurrentScheduler
        return getCurrentScheduler().readVariable(self)
