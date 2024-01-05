from agentgraph.core.mutable import Mutable

class ConversationReader:
    def __init__(self, conv: 'Conversation'):
        self.list = conv.list.copy()

    def size(self) -> int:
        return len(self.list)

    def __getitem__(self, index) -> str:
        return self.list[index]
          
class Conversation(Mutable):
    def __init__(self, msg: str = None):
        super().__init__()
        self.list = []
        if (msg != None):
            self.list.append(msg)
            
    def _snapshot(self) -> ConversationReader:
        return ConversationReader(self)

    def size(self) -> int:
        self.waitForAccess()
        return len(self.list)

    def get(self, index: int):
        self.waitForAccess()
        return self.list[index]
    
    def pop(self, n: int):
        self.waitForAccess()
        for l in range(n):
            self.list.pop()

    def append(self, other: 'Conversation') -> 'Conversation':
        self.waitForAccess()
        conv = Conversation()
        for l in self.list:
            conv.push(l)
        for l in other.list:
            conv.push(l)
        
        return conv

    def summary(self) -> 'Conversation':
        self.waitForAccess()
        val = ""
        for l in self.list:
            val += l;
        return Conversation(val)

    def push(self, text: str):
        self.waitForAccess()
        self.list.append(text)

    def size(self) -> int:
        self.waitForAccess()
        return len(self.list)

    def __getitem__(self, index) -> str:
        self.waitForAccess()
        return self.list[index]
