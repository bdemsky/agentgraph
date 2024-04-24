from typing import Optional
from agentgraph.core.msgseq import MsgSeq

varNameCount = 0

class Var(MsgSeq):
    def __init__(self, name: Optional[str] = None):
        super().__init__()
        if name is None:
            global varNameCount
            name = f"VAR{varNameCount}"
            varNameCount += 1
        self.name = name

    def get_name(self) -> str:
        return self.name

    def is_mutable(self) -> bool:
        return False

    def is_read(self) -> bool:
        return False

    def _get_read_set(self) -> set:
        return { self }

    def exec(self, varsMap: dict):
        lookup = varsMap[self]
        if isinstance(lookup, str):
            return lookup
        else:
            return lookup.exec(varsMap)

    def get_value(self):
        """Method that will return the value the variable is assigned
        by the most recent dispatched task that writes to it.
        """
        
        from agentgraph.exec.scheduler import _get_current_scheduler
        return _get_current_scheduler().read_variable(self)
