import contextvars

class Mutable:
    def __init__(self):
        from agentgraph.exec.scheduler import getCurrentTask
        self._owner = getCurrentTask()
        
    def setOwner(self, task):
        self._owner = task

    def getOwner(self):
        return self._owner
        
    def waitForAccess(self):
        """
        Waits for any potentially conflicting child tasks that
        want/have access to the mutable to finish.
        """
        
        from agentgraph.exec.scheduler import getCurrentTask, getCurrentScheduler
        currTask = getCurrentTask()

        # See if we already own this mutable
        if self._owner == currTask:
            return
        # No, so wait for access
        getCurrentScheduler().objAccess(self)
        # We own this mutable now
        self._owner = currTask
        
    def _snapshot(self):
        pass
