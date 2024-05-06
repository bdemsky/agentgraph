from agentgraph.core.mutable import Mutable

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

    def __add__(a, b):
        """a + b combines a and b into one message."""
        return a.addmsg(b)

    def addmsg(self, o):
        return MsgAdd(self, o)
    
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
        if self.is_exchange():
            raise RuntimeError(f"Can only summarize a message sequences.\n")
        return MsgSummary(self)

    def __pow__(self, b):
        """a ** b means that a is a system message and b is the rest of
        the message sequency."""
        
        return self.system(b)
    
    def system(self, o: 'MsgSeq'):
        return MsgSystem(self, o)

    def __getitem__(self, slicerange):
        return MsgSlice(self, slicerange)
    
    def is_exchange(self) -> bool:
        return False

    def _is_single_msg(self) -> bool:
        return False

    def _get_read_set(self) -> set:
        return set()

    def exec(self, varsMap: dict):
        pass

def _helper_get_read_set(msgseq) -> set:
    if isinstance(msgseq, Mutable):
        return {msgseq}
    elif isinstance(msgseq, MsgSeq):
        return msgseq._get_read_set()
    else:
        return set()
    
def helper_exec(msgseq, varsMap: dict):
    if isinstance(msgseq, str):
        return msgseq
    elif isinstance(msgseq, bytes):
        return msgseq.decode()
    else:
        return msgseq.exec(varsMap)

class MsgSlice(MsgSeq):
    def __init__(self, left: MsgSeq, slicerange: slice):
        self._left = left
        self._range = slicerange

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self._left)

    def exec(self, varsMap:dict):
        l = helper_exec(self._left, varsMap)
        if not isinstance(l, list):
            raise RuntimeError("Slicing applied to non list")
        return l[self._range]
    
def do_extend_list(vleft: list, vright:str):
    if not isinstance(vleft, list):
        raise RuntimeError("Left side of prompt is not list")
    if vleft[-1]["role"] == "user":
        newRole = "assistant"
    elif vleft[-1]["role"] == "assistant":
        newRole = "user"
    else:
        raise RuntimeError("Unhandled role:" + vleft[-1])
    vleft.append({"role": newRole, "content": vright})

def do_extend_list_with_dict(vleft: list, vright:dict):
    vleft.append(vright)

class MsgChooser(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self._left = left
        self._right = right

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self._left).union(_helper_get_read_set(self._right))

    def exec(self, varsMap: dict):
        vleft = helper_exec(self._left, varsMap)
        if not isinstance(self._right, MsgChoice):
            raise RuntimeError("RHS of a > is not a choice")

        if isinstance(vleft, list):
            if len(vleft) == 0:
                return helper_exec(self._right._right, varsMap)
            else:
                return helper_exec(self._right._left, varsMap)
        else:
            raise RuntimeError("LHS of a > is not a list")

class MsgTool(MsgSeq):
    def __init__(self, tool_call_id, function_name, function_response):
        super().__init__()
        self._tool_call_id = tool_call_id
        self._function_name = function_name
        self._function_response = function_response

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self._tool_call_id).union(_helper_get_read_set(self._function_name)).union(_helper_get_read_set(self._function_response))

    def exec(self, varsMap: dict):
        tool_call_id = helper_exec(self._tool_call_id, varsMap)
        function_name = helper_exec(self._function_name, varsMap)
        function_response = helper_exec(self._function_response, varsMap)

        return {"tool_call_id": tool_call_id, "role": "tool", "name": function_name, "content": function_response}

def create_tool_response(tool_call_id, function_name, function_response):
    """Create response from tool. Each item can either be a str or a
    Var that will later resolve to a string.
    """

    return MsgTool(tool_call_id, function_name, function_response)
    
class MsgChoice(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self._left = left
        self._right = right

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self._left).union(_helper_get_read_set(self._right))

    
class MsgConcat(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self._left = left
        self._right = right

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self._left).union(_helper_get_read_set(self._right))

    def exec(self, varsMap: dict):
        vleft = helper_exec(self._left, varsMap)
        vright = helper_exec(self._right, varsMap)
        if isinstance(vright, str):
            do_extend_list(vleft, vright)
            return vleft
        elif isinstance(vright, list):
            for msg in vright:
                do_extend_list(vleft, msg["content"])
            return vleft
        elif isinstance(vright, dict):
            do_extend_list_with_dict(vleft, vright)
            return vleft
        else:
            raise RuntimeError("RHS is neither string or list")

class MsgAdd(MsgSeq):
    def __init__(self, left: MsgSeq, right: MsgSeq):
        super().__init__()
        self._left = left
        self._right = right

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self._left).union(_helper_get_read_set(self._right))

    def exec(self, varsMap: dict):
        vleft = helper_exec(self._left, varsMap)
        vright = helper_exec(self._right, varsMap)
        if isinstance(vright, str) and isinstance(vleft, str):
            return vleft + vright
        else:
            raise RuntimeError("Either LHS or RGS is not string.")
        
class MsgSummary(MsgSeq):
    def __init__(self, msg: MsgSeq):
        super().__init__()
        self.msg = msg

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self.msg)

    def exec(self, varsMap: dict):
        val = helper_exec(self.msg, varsMap)
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

    def _get_read_set(self) -> set:
        return _helper_get_read_set(self._systemMsg).union(_helper_get_read_set(self._conv))
        
    def is_exchange(self) -> bool:
        return True

    def exec(self, varsMap: dict):
        vright = helper_exec(self._conv, varsMap)
        systemmsg = helper_exec(self._systemMsg, varsMap)
        vleft = [{"role": "system", "content": systemmsg}]

        if isinstance(vright, str):
            do_extend_list(vleft, vright)
            return vleft
        elif isinstance(vright, list):
            for msg in vright:
                do_extend_list(vleft, msg["content"])
            return vleft
        else:
            raise RuntimeError("RHS is neither string or list")
