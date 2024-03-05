from agentgraph.core.mutable import Mutable
from agentgraph.core.msgseq import MsgSeq

class ConversationReader:
    def __init__(self, conv: 'Conversation'):
        self._system = conv._system
        self._sent = conv._sent.copy()
        self._recv = conv._recv.copy()

          
class Conversation(Mutable, MsgSeq):
    def __init__(self, system = None, prompt = None, owner = None):
        super().__init__(owner)
        super(Mutable, self).__init__()
        self._system = system
        self._recv = []
        self._sent = []
        if prompt is not None:
            self._sent.push(prompt)

    def loadConv(self, conv: list):
        self._system = None
        self._recv = []
        self._sent = []
        for msg in conv:
            sender = msg["role"]
            if sender == "user":
                self._sent.append(msg["content"])
            elif sender == "assistant":
                self._recv.append(msg["content"])
            elif sender == "system":
                self._system = msg["content"]    

    def copyState(self, conv):
        self._system = conv._system
        self._sent = conv._sent.copy()
        self._recv = conv._recv.copy()
            
    def _snapshot(self) -> ConversationReader:
        return ConversationReader(self)

    def sizeSent(self) -> int:
        self.waitForAccess()
        return len(self._sent)

    def sizeRecv(self) -> int:
        self.waitForAccess()
        return len(self._recv)

    def getSent(self, index: int):
        self.waitForAccess()
        return self._sent[index]

    def getRecv(self, index: int):
        self.waitForAccess()
        return self._recv[index]
    
    def pop(self, n: int):
        self.waitForAccess()
        recv_size = len(self._recv)
        sent_size = len(self._sent)
        for l in range(n):
            if recv_size == sent_size:
                self._recv.pop()
                recv_size-=1;
            else:
                self._sent.pop()
                sent_size-=1;
                
    def push(self, text: str):
        self.waitForAccess()
        if len(self._recv) == len(self._sent):
            self._sent.append(text)
        else:
            self._recv.append(text)

    def exec(self, varMaps:dict):
        l = list()
        if self._system is not None:
            l.append({"role": "system", "content": self._system})
        for i in range(len(self._sent)):
            l.append({"role": "user", "content": self._sent[i]})
            if i < len(self._recv):
                l.append({"role": "assistant", "content" : self._recv[i]})
            
        return l
            
    def pushRound(self, sent: str, recv: str):
        self.waitForAccess()
        self._sent.append(sent)
        self._recv.append(recv)

