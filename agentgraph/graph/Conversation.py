class ConversationReader:
    def __init__(self, conv: 'Conversation'):
        self.__conv = __conv

    def size(self):
        return self.__conv.size()

    def __getitem__(self, index):
        return self.__conv[index]
          
class Conversation:
    def __init__(self):
        self.list = []
        pass

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
