import agentgraph
import os
import time
import re
import subprocess

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
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

sysA = prompts.load_prompt("SystemA")
pA = prompts.load_prompt("PromptA")
ovarA = agentgraph.Var("OutA")
gdb_out = agentgraph.Var("gdb_out")
pgdb = prompts.load_prompt("PromptGDB", {gdb_out})
varmap = agentgraph.VarMap()
convA = varmap.map_to_conversation("AgentA")
convGDB = varmap.map_to_conversation("GDB")

while True:
    agentA = agentgraph.create_llm_agent(ovarA, conversation = convA, msg = sysA > pA + convGDB & convA)
    scheduler.add_task(agentA.start, varmap)
    varMap = None
    agentGDB = agentgraph.create_python_agent(run_gdb, pos=[ovarA], out=[gdb_out])
    scheduler.add_task(agentGDB.start)
    gdb_output = gdb_out.get_value()
    if not gdb_output:
        break
    convGDB.get_value().push(gdb_output)
    print(gdb_output, end='')

scheduler.shutdown() 
