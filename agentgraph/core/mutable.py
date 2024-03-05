import contextvars

class Mutable:
    def __init__(self, owner: 'Mutable' = None):
        """
        A mutable can be owned by either another mutable or a task.
        It is an ownership root iff it is owned by a task.
        """
        if owner != None:
            root = owner.getRootObject()
            root.waitForAccess()
            self._owner = root
            root._size += 1
        else:
            from agentgraph.exec.scheduler import getCurrentTask
            self._owner = getCurrentTask()

        self._size = 1
        

    def setOwningObject(self, owner: 'Mutable'):
        # Merge ownership trees with the union in union find
        x = owner.getRootObject()
        y = self.getRootObject()
        if x == y:
            return 

        # union by size
        if x._size < y._size:
            x, y = y, x

        # get ownership of roots to be merged
        from agentgraph.exec.scheduler import getCurrentScheduler
        x.waitForAccess()
        y.waitForAccess()
        y._owner = x
        x._size += y._size
        getCurrentScheduler().mergeObjAccesses(y, x)
    
    def getRootObject(self) -> 'Mutable':
        # find ownership root with the find in union find     
        root = self
        while isinstance(root._owner, Mutable):
            root = self._owner

        # path compression
        obj = self
        while isinstance(obj._owner, Mutable):
            owner = obj._owner
            obj._owner = root
            obj = owner

        return root

    def getOwningTask(self) -> 'ScheduleNode':
        root = self.getRootObject()
        return root._owner
    
    def setOwningTask(self, task: 'ScheduleNode'):
        root = self.getRootObject()
        root._owner = task
        
    def waitForAccess(self):
        """
        Waits for any potentially conflicting child tasks that
        want/have access to the mutable to finish.
        """
        
        from agentgraph.exec.scheduler import getCurrentTask, getCurrentScheduler
        currTask = getCurrentTask()
        root = self.getRootObject()

        # See if we already own this mutable
        if root._owner == currTask:
            return
        # No, so wait for access
        getCurrentScheduler().objAccess(root)
        # We own this mutable now
        root._owner = currTask

    def _snapshot(self):
        pass
