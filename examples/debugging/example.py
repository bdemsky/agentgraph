import agentgraph
import os
import time
import re
import subprocess

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.getRootScheduler(model)
prompts = agentgraph.Prompts("./examples/debugging/prompts/")

gdb_process = None
def run_gdb(scheduler, cmd):
    global gdb_process
    print(cmd)
    if gdb_process == None:
        if not cmd.startswith('gdb'):
            return [None]
        gdb_process = subprocess.Popen(cmd.split(), cwd="./examples/debugging/testdirectory/", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    else:
        gdb_process.stdin.write(bytes(cmd + '\n', 'utf-8'))
        gdb_process.stdin.flush()
        if cmd == 'q' or cmd == 'quit':
            gdb_process.wait()
            return [None]
    output = ''
    while gdb_process.stdout.peek(6).decode() != '(gdb) ':
        output += gdb_process.stdout.readline().decode()
    else:
        output += gdb_process.stdout.read(6).decode()
    return [output]

sysA = prompts.loadPrompt("SystemA")
pA = prompts.loadPrompt("PromptA")
ovarA = agentgraph.Var("OutA")
gdb_out = agentgraph.Var("gdb_out")
pgdb = prompts.loadPrompt("PromptGDB", {gdb_out})
varmap = agentgraph.VarMap()
convA = varmap.mapToConversation("AgentA")
convGDB = varmap.mapToConversation("GDB")

while True:
    agentA = agentgraph.createLLMAgent(ovarA, conversation = convA, msg = sysA > pA + convGDB & convA)
    scheduler.addTask(agentA.start, varmap)
    varMap = None
    agentGDB = agentgraph.createPythonAgent(run_gdb, pos=[ovarA], out=[gdb_out])
    scheduler.addTask(agentGDB.start)
    gdb_output = gdb_out.getValue()
    if not gdb_output:
        break
    convGDB.getValue().push(gdb_output)
    print(gdb_output, end='')

scheduler.shutdown() 
