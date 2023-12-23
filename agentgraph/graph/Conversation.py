class ConversationReader:
    def __init__(self, conv: 'Conversation'):
        self.list = conv.list.copy()

    def size(self) -> int:
        return len(self.list)

    def __getitem__(self, index) -> str:
        return self.list[index]
          
class Conversation:
    def __init__(self):
        self.list = []

    def snapshot(self) -> ConversationReader:
        return ConversationReader(self)
        
    def pop(self, n: int):
        for l in range(n):
            self.list.pop()

    def push(self, text: str):
        self.list.append(text)

    def size(self) -> int:
        return len(self.list)

    def __getitem__(self, index) -> str:
        return self.list[index]
