from typing import Optional, Union
import contextvars
import agentgraph

class Mutable:
    def __init__(self, owner: 'Optional[Mutable]' = None):
        """
        A mutable can be owned by either another mutable or a task.
        It is an ownership root iff it is owned by a task.
        """
        self._size = 1
        
        if owner is not None:
            root = owner.getRootObject()
            root.waitForAccess()
            self._owner: Union['Mutable', 'agentgraph.exec.scheduler.ScheduleNode'] = root
            root._size += 1
        else:
            from agentgraph.exec.scheduler import getCurrentTask
            self._owner = getCurrentTask()
        

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
        scheduler = getCurrentScheduler()
        if scheduler is not None:
            x.waitForAccess()
            y.waitForAccess()
            scheduler.mergeObjAccesses(y, x)
        y._owner = x
        x._size += y._size
    
    def getRootObject(self) -> 'Mutable':
        # find ownership root with the find in union find     
        root: Mutable = self
        while True:
            nextOwner = root._owner
            if isinstance(nextOwner, Mutable):
                root = nextOwner
            else:
                break

        # path compression
        obj: Mutable = self
        while True:
            nextOwner = obj._owner
            if isinstance(nextOwner, Mutable):
                obj._owner = root
                obj = nextOwner
            else:
                break
            
        return root

    def getOwningTask(self) -> Optional['agentgraph.exec.scheduler.ScheduleNode']:
        root = self.getRootObject()
        assert root._owner is None or isinstance(root._owner, agentgraph.exec.scheduler.ScheduleNode)
        return root._owner
    
    def setOwningTask(self, task: 'agentgraph.exec.scheduler.ScheduleNode'):
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
    
    def waitForReadAccess(self):
        from agentgraph.exec.scheduler import getCurrentTask, getCurrentScheduler
        currTask = getCurrentTask()
        root = self.getRootObject()

        # See if we already own this mutable
        if root._owner == currTask:
            return
        # No, so wait for access
        getCurrentScheduler().objAccess(root, True)
        # We own this mutable now
        # root._owner = currTask

    def _snapshot(self):
        pass
    
    def _getReadOnlyProxy(self):
        raise NotImplementedError

class ReadOnly:
    def __init__(self, mutable: 'Union[Mutable, agentgraph.core.var.Var]'):
        self._mutable = mutable
    
    def getMutable(self):
        return self._mutable

class ReadOnlyProxy:
    _mutable = None