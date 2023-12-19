class ConversationReader:
    def __init__(self, conv: 'Conversation'):
        self.list = conv.list.copy()

    def size(self):
        return len(self.list)

    def __getitem__(self, index):
        return self.list[index]
          
class Conversation:
    def __init__(self):
        self.list = []

    def getReader(self) -> ConversationReader:
        return ConversationReader(self)
        
    def pop(self, n: int):
        for l in range(n):
            self.list.pop()

    def push(self, text):
        self.list.append(text)

    def size(self):
        return len(self.list)

    def __getitem__(self, index):
        return self.list[index]
