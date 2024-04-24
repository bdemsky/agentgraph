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
            root = owner._get_root_object()
            root.wait_for_access()
            self._owner: Union['Mutable', 'agentgraph.exec.scheduler.ScheduleNode'] = root
            root._size += 1
        else:
            from agentgraph.exec.scheduler import _get_current_task
            self._owner = _get_current_task()
        

    def set_owning_object(self, owner: 'Mutable'):
        # Merge ownership trees with the union in union find
        x = owner._get_root_object()
        y = self._get_root_object()
        if x == y:
            return 

        # union by size
        if x._size < y._size:
            x, y = y, x

        # get ownership of roots to be merged
        from agentgraph.exec.scheduler import _get_current_scheduler
        scheduler = _get_current_scheduler()
        if scheduler is not None:
            x.wait_for_access()
            y.wait_for_access()
            scheduler._merge_obj_accesses(y, x)
        y._owner = x
        x._size += y._size
    
    def _get_root_object(self) -> 'Mutable':
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
        root = self._get_root_object()
        assert root._owner is None or isinstance(root._owner, agentgraph.exec.scheduler.ScheduleNode)
        return root._owner
    
    def setOwningTask(self, task: 'agentgraph.exec.scheduler.ScheduleNode'):
        root = self._get_root_object()
        root._owner = task
        
    def wait_for_access(self):
        """
        Waits for any potentially conflicting child tasks that
        want/have access to the mutable to finish.
        """
        
        from agentgraph.exec.scheduler import _get_current_task, _get_current_scheduler
        currTask = _get_current_task()
        root = self._get_root_object()

        # See if we already own this mutable
        if root._owner == currTask:
            return
        # No, so wait for access
        _get_current_scheduler().objAccess(root)
        # We own this mutable now
        root._owner = currTask
    
    def wait_for_read_access(self):
        from agentgraph.exec.scheduler import _get_current_task, _get_current_scheduler
        currTask = _get_current_task()
        root = self._get_root_object()

        # See if we already own this mutable
        if root._owner == currTask:
            return
        # No, so wait for access
        _get_current_scheduler().objAccess(root, True)
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