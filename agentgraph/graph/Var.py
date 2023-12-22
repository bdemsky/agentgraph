class Var:
    def __init__(self, _name: str):
        self.name = _name

    def getName(self) -> str:
        return self.name

    def isMutable(self) -> bool:
        return False

    def isRead(self) -> bool:
        return False
