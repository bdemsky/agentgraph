import agentgraph
import os
import time
import re
import subprocess
import json

def get_current_weather(location: str, format: str):
    '''Get the current weather

    Arguments:
    location --- The city and state, e.g. San Francisco, CA
    format --- The temperature unit to use. Infer this from the users location.
    '''
    return "sunny"

model = agentgraph.LLMModel("https://demskygroupgpt4.openai.azure.com/", os.getenv("OPENAI_API_KEY"), "GPT4-8k", "GPT-32K", 34000, "2023-12-01-preview")
scheduler = agentgraph.getRootScheduler(model)
cur_dir = os.path.dirname(os.path.abspath(__file__))
prompts = agentgraph.Prompts(cur_dir + "/prompts/")
testdir_path = cur_dir + "/testdirectory/"

ovarFix = agentgraph.Var("OutCall")
ovarA, ovarA2 = agentgraph.Var("OutA"), agentgraph.Var("OutA2")
callA, callA2 = agentgraph.Var("CallA"), agentgraph.Var("CallA2")

varmap = agentgraph.VarMap()
convA = varmap.mapToConversation("AgentA")

pA, pA2 = prompts.loadPrompt("PromptA"), prompts.loadPrompt("PromptA2")
sysA = prompts.loadPrompt("SystemA")

agentA = agentgraph.createLLMAgentWithFuncs(ovarA, callVar=callA, agentFuncs=[get_current_weather], conversation=convA, msg=sysA > pA) |\
         agentgraph.createLLMAgentWithFuncs(ovarA2, callVar=callA2, agentFuncs=[get_current_weather], conversation=convA, msg=sysA > (pA + pA2) & convA)

# alternatively, tools can be constructed from jinja templates
# tools = agentgraph.ToolLists(cur_dir + "/tools/")
# funcGetWeather = tools.loadToolList("get_current_weather")
# agentA = agentgraph.createLLMAgent(ovarA, callVar=callA, tools=funcGetWeather, toolHandlers={"get_current_weather": get_current_weather}, conversation=convA, msg=sysA > pA) |\
#          agentgraph.createLLMAgent(ovarA2, callVar=callA2, tools=funcGetWeather, toolHandlers={"get_current_weather": get_current_weather}, conversation=convA, msg=sysA > (pA + pA2) & convA)

scheduler.addTask(agentA.start, varmap)
print("LLM: ", ovarA.getValue(), "\n", callA.getValue())
print("LLM: ", ovarA2.getValue(), "\n", callA2.getValue())

scheduler.shutdown() 
