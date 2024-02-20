class VarSet(set):
    def __init__(self, iter = None):
        if iter is None:
            super().__init__()
        else:
            super().__init__(iter)
