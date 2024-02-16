class MsgSeq:
    def __init__(self):
        pass

    def __or__(a, b):
        """a | b first processes a and if it is empty, then processes b"""
        return a.msgchoice(b)

    def msgchoice(self, b):
        return MsgChoice(self, b)

    def __gt__(a, b):
        return a.choice(b)
    
    def choice(self, b):
        return MsgChooser(self, b)    
    
    def __and__(a, b):
        """a & b adds message b to the conversation,"""
        return a.concat(b)

    def concat(self, o):
        return MsgConcat(self, o)

    def __invert__(o):
        """~a summarizes the messages in the sequence a into a single
        message."""
        
        return o.summarize()
    
    def summarize(self):
        if self.isExchange():
            raise RuntimeError(f"Can only summarize a message sequences.\n")
        return MsgSummary(self)

    def __pow__(self, b):
        """a ** b means that a is a system message and b is the rest of
        the message sequency."""
        
        return self.system(b)
    
    def system(self, o: 'MsgSeq'):
        return MsgSystem(self, o)

    def getitem(self, slicerange):
        return MsgSlice(self, slicerange)
    
    def isExchange(self) -> bool:
        return False

    def isSingleMsg(self) -> bool:
        return False

    def getVars(self) -> set:
        return set()

    def exec(self, varsMap: dict):
        pass

class MsgSlice(MsgSeq):
    def __init__(self, left: MsgSeq, slicerange: slice):
        self._left = left
        self._range = slicerange

    def getVars(self) -> set:
        return self._left.getVars()

    def exec(self, varsMap:dict):
        l = self._left.exec(varsMap)
        if not isinstance(l, list):
            raise RuntimeError("Slicing applied to non list")
        return l[self._range]
    
def doExtendList(vleft: list, vright:str):
    if not isinstance(vleft, list):
        raise RuntimeError("Left side of prompt is not list")
    if vleft[-1]["role"] == "user":
        newRole = "assistant"
    else:
        newRole = "user"
    vleft.append({"role": newRole, "content": vright})    

class MsgChooser(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self._left = left
        self._right = right

    def getVars(self) -> set:
        return self._left.getVars().union(self._right.getVars())

    def exec(self, varsMap: dict):
        vleft = self._left.exec(varsMap)
        if not isinstance(self._right, MsgChoice):
            raise RuntimeError("RHS of a > is not a choice")

        if isinstance(vleft, list):
            if len(vleft) == 0:
                return self._right._right.exec(varsMap)
            else:
                return self._right._left.exec(varsMap)
        else:
            raise RuntimeError("LHS of a > is not a list")
    
    
class MsgChoice(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self._left = left
        self._right = right

    def getVars(self) -> set:
        return self._left.getVars().union(self._right.getVars())

    
class MsgConcat(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self._left = left
        self._right = right

    def getVars(self) -> set:
        return self._left.getVars().union(self._right.getVars())

    def exec(self, varsMap: dict):
        vleft = self._left.exec(varsMap)
        vright = self._right.exec(varsMap)
        if isinstance(vright, str):
            doExtendList(vleft, vright)
            return vleft
        elif isinstance(vright, list):
            for msg in vright:
                doExtendList(vleft, msg["content"])
            return vleft
        else:
            raise RuntimeError("RHS is neither string or list")
        
class MsgSummary(MsgSeq):
    def __init__(self, msg: MsgSeq):
        super().__init__()
        self.msg = msg

    def getVars(self) -> set:
        return self.msg.getVars()

    def exec(self, varsMap: dict):
        val = self.msg.exec(varsMap)
        response = ""
        for msg in val:
            if msg["role"] == "assistant":
                response += msg["content"]
        
        return response

    
class MsgSystem(MsgSeq):
    def __init__(self, systemMsg: MsgSeq, conv: MsgSeq):
        super().__init__()
        self._systemMsg = systemMsg
        self._conv = conv

    def getVars(self) -> set:
        return self._systemMsg.getVars().union(self._conv.getVars())
        
    def isExchange(self) -> bool:
        return True

    def exec(self, varsMap: dict):
        vright = self._conv.exec(varsMap)
        systemmsg = self._systemMsg.exec(varsMap)
        vleft = [{"role": "system", "content": systemmsg}]

        if isinstance(vright, str):
            doExtendList(vleft, vright)
            return vleft
        elif isinstance(vright, list):
            for msg in right:
                doExtendList(vleft, msg["content"])
            return vleft
        else:
            raise RuntimeError("RHS is neither string or list")
