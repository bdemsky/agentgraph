from agentgraph.core.mutable import Mutable
from agentgraph.core.msgseq import MsgSeq

class ConversationReader:
    def __init__(self, conv: 'Conversation'):
        self._system = conv._system
        self._msgs = conv._msgs.copy()

class Conversation(Mutable, MsgSeq):
    def __init__(self, system = None, prompt = None, owner = None):
        super().__init__(owner)
        super(Mutable, self).__init__()
        self._system = system
        self._msgs = []
        if prompt is not None:
            self._msgs.push({"role": "user", "content": prompt})

    def load_conv(self, conv: list):
        self.wait_for_access()
        self._system = None
        self._msgs = []
        for msg in conv:
            sender = msg["role"]
            if sender == "system":
                self._system = msg["content"]
            else:
                self._msgs.append(msg)

    def copy_state(self, conv):
        self._system = conv._system
        self._msgs = conv._msgs.copy()

    def _snapshot(self) -> ConversationReader:
        return ConversationReader(self)

    def size_msgs(self) -> int:
        self.wait_for_access()
        return len(self._msgs)

    def get_msgs(self, index: int):
        self.wait_for_access()
        return self._msgs[index]

    def pop(self, n: int):
        self.wait_for_access()
        for l in range(n):
            self._msgs.pop()

    def push(self, text: str):
        self.wait_for_access()
        if len(self._msgs) == 0:
            self._msgs.append({"role": "user", "content": text})
        else:
            lastrole = self._msgs[-1].get_role()
            if lastrole == "user":
                newrole = "assistant"
            elif lastrole == "assistant":
                newrole = "user"
            elif lastrole == "function":
                newrole = "assistant"
        self._msgs.append({"role": newrole, "content":text})

    def push_item(self, item):
        self.wait_for_access()
        self._msgs.append(item)

    def exec(self, varMaps:dict):
        l = list()
        if self._system is not None:
            l.append({"role": "system", "content": self._system})
        for i in range(len(self._msgs)):
            l.append(self._msgs[i])

        return l

