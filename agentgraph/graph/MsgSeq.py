class MsgSeq:
    def __init__(self):
        pass


class MsgConcat(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self.left = left
        self.right = right
        
class MsgSummary(MsgSeq):
    def __init__(self, msg: MsgSeq):
        super().__init__()
        self.msg = msg

    
class MsgInterleave(MsgSeq):
    def __init__(self, user: MsgSeq, assistant: MsgSeq):
        super().__init__()
        self.user = user
        self.assistant = assistant

        
class MsgSystem(MsgSeq):
    def __init__(self, system: MsgSeq, conv: MsgSeq):
        super().__init__()
        self.system = system
        self.conv = conv
