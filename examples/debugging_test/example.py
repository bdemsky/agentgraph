import agentgraph
import os
import time
import re
import subprocess

from file_utils import *

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000)
scheduler = agentgraph.get_root_scheduler(model)
cur_dir = os.path.dirname(os.path.abspath(__file__))
prompts = agentgraph.Prompts(cur_dir + "/prompts/")
testdir_path = cur_dir + "/testdirectory/"

def run_gdb(scheduler, cmd, gdb_process):
    print(cmd)
    if gdb_process == None:
        if not cmd.startswith('gdb'):
            return [None, gdb_process]
        gdb_process = subprocess.Popen(cmd.split(), cwd=testdir_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    else:
        gdb_process.stdin.write(bytes(cmd + '\n', 'utf-8'))
        gdb_process.stdin.flush()
        if cmd == 'q' or cmd == 'quit':
            gdb_process.wait()
            return [None, gdb_process]
    output = ''
    while gdb_process.stdout.peek(6).decode() != '(gdb) ':
        output += gdb_process.stdout.readline().decode()
    else:
        output += gdb_process.stdout.read(6).decode()
    return [output, gdb_process]

def chat_to_fs(scheduler, chat: str, fileStore: FileStore):
    for fileName, fileContent in parse_chat(chat):
        fileStore[fileName] = fileContent
        print(f"parsed file {fileName} to be save")
    # we do not write to the fs for now
    fileStore.write_files(testdir_path)

def run_test(scheduler, fileStore: FileStore) -> str:
    msgs = ""
    try:
        p = subprocess.run(['bash', 'test.sh'], cwd=testdir_path, timeout=5, capture_output=True)
    except subprocess.TimeoutExpired:
        print(f"test.sh Timeout")
        if p is None:
          msgs = f"test.sh failed due to a timeout.  There was no output."
        else:
          msgs = f"test.sh failed due to a timeout and outputted:\n" + p.stdout.decode() + p.stderr.decode()     
    else:
        if (p.returncode==0):
            print(f"test.sh passed!\n")
            msgs = f"The output of running test.sh was:\n"+p.stdout.decode() + p.stderr.decode()
        else: 
            print(f"test.sh failed!\n")
            msgs = f"test.sh failed with the following message:\n" + p.stdout.decode() + p.stderr.decode()
    return [msgs]

ovarFix = agentgraph.Var("OutFix")
ovarA = agentgraph.Var("OutA")
ovarGDB = agentgraph.Var("OutGDB")
ovarTest = agentgraph.Var("OutTest")

varmap = agentgraph.VarMap()
convA = varmap.mapToConversation("AgentA")
convGDB = varmap.mapToConversation("GDB")
processGDB = varmap.mapToMutable("ProcessGDB", None)

store = FileStore()
read_from_fs(store, testdir_path)
fileStore = varmap.mapToFileStore("FileStore", store)

sysA = prompts.load_prompt("SystemA")
pA = prompts.load_prompt("PromptA", {fileStore, ovarTest})
pFix = prompts.load_prompt("PromptFix")

agentA = agentgraph.create_python_agent(run_test, pos=[fileStore], out=[ovarTest])
scheduler.addTask(agentA.start, varmap)

while True:
    agentPair = \
        agentgraph.create_llm_agent(ovarA, conversation = convA, msg = sysA > pA + convGDB & convA) | \
        agentgraph.create_python_agent(run_gdb, pos=[ovarA, processGDB], out=[ovarGDB, processGDB])
    scheduler.addTask(agentPair.start)
    print("LLM: ", ovarA.get_value())
    gdb_output = ovarGDB.get_value()
    if not gdb_output:
        break
    convGDB.get_value().push(gdb_output)
    print("GDB: ", gdb_output)

agentPair = \
    agentgraph.create_llm_agent(ovarFix, conversation = convA, msg = sysA > pA + convGDB + pFix & convA) | \
    agentgraph.create_python_agent(chat_to_fs, pos=[ovarFix, fileStore]) | \
    agentgraph.create_python_agent(run_test, pos=[fileStore], out=[ovarTest])

scheduler.addTask(agentPair.start)
print("LLM: ", ovarFix.get_value())
print("Test result: ", ovarTest.get_value())

scheduler.shutdown() 
