import agentgraph
import os
import time
from agentgraph.core.mutable import Mutable, ReadOnly, ReadOnlyProxy

def createMutable(scheduler) -> list:
    print('createMutable')
    time.sleep(0.5)
    return [TestMutable()]

def testFuncA1(scheduler, m, start) -> list:
    time.sleep(0.5)
    print("TestA", f'{time.time() - start:.2f}', m)
    time.sleep(0.5)
    return []

def testFuncA2(scheduler, m, start) -> list:
    print("TestA2")
    scheduler.run_python_agent(testFuncA1, pos=[m, start]) # okay
    time.sleep(2)
    return [m] # BAD

def testFuncA3(scheduler, ro, m, start) -> list:
    time.sleep(0.5)
    print("TestA3", f'{time.time() - start:.2f}', ro, m)
    time.sleep(0.5)
    return []

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
start = time.time()

class TestReadOnlyProxy(ReadOnlyProxy):
    def __init__(self, mutable):
        self._mutable = mutable
    
    def __repr__(self):
        return 'ReadOnlyProxy'

class TestMutable(Mutable):
    def _getReadOnlyProxy(self):
        return TestReadOnlyProxy(self)
    
    def __repr__(self):
        return 'Mutable'

mutable = TestMutable()
print('START')
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mutable), mutable, start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mutable), ReadOnly(mutable), start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mutable), mutable, start])
scheduler.run_python_agent(testFuncA3, pos=[mutable, mutable, start])
scheduler.run_python_agent(testFuncA3, pos=[mutable, ReadOnly(mutable), start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mutable), mutable, start])
mutable.wait_for_read_access()
print('TestB', time.time() - start)
mutable.wait_for_access()

proxy = mutable._getReadOnlyProxy()
scheduler.run_python_agent(testFuncA3, pos=[proxy, mutable, start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.run_python_agent(testFuncA3, pos=[proxy, ReadOnly(mutable), start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mutable), mutable, start])
scheduler.run_python_agent(testFuncA3, pos=[mutable, mutable, start])
scheduler.run_python_agent(testFuncA3, pos=[mutable, proxy, start])
scheduler.run_python_agent(testFuncA1, pos=[proxy, start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.run_python_agent(testFuncA3, pos=[proxy, mutable, start])
mutable.wait_for_read_access()
print('TestB', time.time() - start)
mutable.wait_for_access()

mvar = scheduler.run_python_agent(createMutable, numOuts=1)
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start])
scheduler.run_python_agent(testFuncA1, pos=[mvar, start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start])
mvar.get_value()

varmap = agentgraph.VarMap()
mvar = varmap.mapToMutable('mut', TestMutable())
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start], vmap=varmap)
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start], vmap=varmap)
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start], vmap=varmap)
scheduler.run_python_agent(testFuncA1, pos=[mvar, start], vmap=varmap)
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start], vmap=varmap)
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start], vmap=varmap)
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.run_python_agent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.run_python_agent(testFuncA3, pos=[ReadOnly(mvar), mvar, start], vmap=varmap)
mvar.get_value()

#scheduler.run_python_agent(testFuncA2, pos=[ReadOnly(mvar), start], vmap=varmap, numOuts=1) # BAD

scheduler.shutdown()