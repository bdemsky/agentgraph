class MsgSeq:
    def __init__(self):
        pass

    def __add__(a, b):
        return a.concat(b)

    def concat(self, o: 'MsgSeq'):
        if self.isExchange() or o.isExchange():
            raise RuntimeException(f"Can only concat/+ two message sequences.\n")

        return MsgConcat(self, o)

    def __invert__(o):
        """~a summarizes the messages in the sequence a into a single
        message."""
        
        return o.summarize()
    
    def summarize(self):
        if self.isExchange():
            raise RuntimeException(f"Can only summarize a message sequences.\n")
        return MsgSummary(self)

    def __and__(a, b):
        """a & b interleave the messages in message sequence a and b
        such that a's messages are user messages and b's are assistant
        messages."""
        
        return a.interleave(b)
    
    def interleave(self, o: 'MsgSeq'):
        if self.isExchange() or o.isExchange():
            raise RuntimeException(f"Can only interleave message sequences.\n")
        return MsgInterleave(self, o)

    def __gt__(a, b):
        """a > b means that a is a system message and b is the rest of
        the message sequency."""
        
        return a.system(b)
    
    def system(self, o: 'MsgSeq'):
        if not o.isExchange() and not o.isSingleMsg():
            raise RuntimeException(f"The second part of a system operator must be a message sequence.\n")
        return MsgSystem(self, o)

    def isExchange(self) -> bool:
        return False

    def isSingleMsg(self) -> bool:
        return False

    def getVars(self) -> set:
        return None

    def exec(self, varsMap: dict):
        pass
    
class MsgConcat(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self.left = left
        self.right = right

    def getVars(self) -> set:
        return self.left.getVars().union(self.right.getVars())

    def exec(self, varsMap: dict):
        vleft = left.exec(dict)
        vright = right.exec(dict)
        return vleft.append(vright)
    
class MsgSummary(MsgSeq):
    def __init__(self, msg: MsgSeq):
        super().__init__()
        self.msg = msg

    def getVars(self) -> set:
        return self.msg.getVars()

    def exec(self, varsMap: dict):
        val = msg.exec(dict)
        return val.summary()
    
class MsgInterleave(MsgSeq):
    def __init__(self, user: MsgSeq, assistant: MsgSeq):
        super().__init__()
        self.user = user
        self.assistant = assistant

    def getVars(self) -> set:
        return self.user.getVars().union(self.assistant.getVars())
        
    def isExchange(self) -> bool:
        return True

    def exec(self, varsMap: dict):
        userseq = self.user.exec(dict)
        assistantseq = self.assistant.exec(dict)
        seq = []
        for i in range(userseq.size()):
            message = userseq.get(i)
            seq.append({"role": "user", "content": message})
            if i < assistantseq.size():
                message = assistantseq.get(i)
                seq.append({"role": "assistant", "content": message})
        return seq
                
class MsgSystem(MsgSeq):
    def __init__(self, system: MsgSeq, conv: MsgSeq):
        super().__init__()
        self.system = system
        self.conv = conv

    def getVars(self) -> set:
        return self.system.getVars().union(self.conv.getVars())
        
    def isExchange(self) -> bool:
        return True

    def exec(self, varsMap: dict):
        conv= self.conv.exec(dict)
        systemmsg = self.system.exec(dict)
        sys = [{"role": "system", "content": systemmsg}]
        if self.conv.isSingleMsg():
            return sys + [{"role": "system", "content": conv.get(0)}]
        else:
            return sys + conv
