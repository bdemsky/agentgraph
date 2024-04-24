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

    def load_conv(self, conv: list):
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

    def copy_state(self, conv):
        self._system = conv._system
        self._sent = conv._sent.copy()
        self._recv = conv._recv.copy()
            
    def _snapshot(self) -> ConversationReader:
        return ConversationReader(self)

    def size_sent(self) -> int:
        self.wait_for_access()
        return len(self._sent)

    def size_recv(self) -> int:
        self.wait_for_access()
        return len(self._recv)

    def get_sent(self, index: int):
        self.wait_for_access()
        return self._sent[index]

    def get_recv(self, index: int):
        self.wait_for_access()
        return self._recv[index]
    
    def pop(self, n: int):
        self.wait_for_access()
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
        self.wait_for_access()
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
            
    def push_round(self, sent: str, recv: str):
        self.wait_for_access()
        self._sent.append(sent)
        self._recv.append(recv)

