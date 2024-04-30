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
convA = agentgraph.Conversation()
gdb_output = None

while True:
    ovarA = scheduler.run_llm_agent(conversation = convA, msg = convA > convA & gdb_output | sysA ** pA)
    gdb_out = scheduler.run_python_agent(run_gdb, pos=[ovarA], numOuts=1)
    gdb_output = gdb_out.get_value()
    if not gdb_output:
        break
    print(gdb_output, end='')

scheduler.shutdown() 
