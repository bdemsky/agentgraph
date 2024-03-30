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
    print("TestA", time.time() - start, m)
    time.sleep(0.5)
    return []

def testFuncA2(scheduler, m, start) -> list:
    print("TestA2")
    scheduler.runPythonAgent(testFuncA1, pos=[m, start]) # okay
    time.sleep(2)
    return [m] # BAD

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
start = time.time()

class TestMutable(Mutable):
    def _getReadOnlyProxy(self):
        return ReadOnlyProxy()

mutable = TestMutable()
print('START')
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.runPythonAgent(testFuncA1, pos=[mutable, start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mutable), start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mutable), start])
mutable.waitForAccess()
print('TestB', time.time() - start)

mvar = scheduler.runPythonAgent(createMutable, numOuts=1)
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.runPythonAgent(testFuncA1, pos=[mvar, start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start])
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start])
mvar.getValue()

varmap = agentgraph.VarMap()
mvar = varmap.mapToMutable('mut', TestMutable())
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.runPythonAgent(testFuncA1, pos=[mvar, start], vmap=varmap)
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
scheduler.runPythonAgent(testFuncA1, pos=[ReadOnly(mvar), start], vmap=varmap)
mvar.getValue()

#scheduler.runPythonAgent(testFuncA2, pos=[ReadOnly(mvar), start], vmap=varmap, numOuts=1) # BAD

scheduler.shutdown()