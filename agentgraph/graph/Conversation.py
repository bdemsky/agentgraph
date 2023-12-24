class ConversationReader:
    def __init__(self, conv: 'Conversation'):
        self.list = conv.list.copy()

    def size(self) -> int:
        return len(self.list)

    def __getitem__(self, index) -> str:
        return self.list[index]
          
class Conversation:
    def __init__(self, msg: str = None):
        self.list = []
        if (msg != None):
            self.list.append(msg)
            
    def snapshot(self) -> ConversationReader:
        return ConversationReader(self)
        
    def pop(self, n: int):
        for l in range(n):
            self.list.pop()

    def append(self, other: 'Conversation') -> 'Conversation':
        conv = Conversation()
        for l in self.list:
            conv.push(l)
        for l in other.list:
            conv.push(l)
        
        return conv

    def summary(self) -> 'Conversation':
        val = ""
        for l in self.list:
            val += l;
        return Conversation(val)

    def push(self, text: str):
        self.list.append(text)

    def size(self) -> int:
        return len(self.list)

    def __getitem__(self, index) -> str:
        return self.list[index]
