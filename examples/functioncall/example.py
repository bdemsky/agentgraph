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
    return "70°F, cloudy"

def get_n_day_weather_forecast(location: str, format: str, num_days: int):
    '''Get an N-day weather forecast

    Arguments:
    location --- The city and state, e.g. San Francisco, CA
    format --- The temperature unit to use. Infer this from the users location.
    num_days --- The number of days to forecast
    '''
    return ["70°F, cloudy", "75°F, sunny"]

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

# construct tools from python functions
# ToolsWeather = map(agentgraph.ToolReflect, [get_current_weather, get_n_day_weather_forecast])

# alternatively, tools can be constructed from jinja templates
toolLoader = agentgraph.ToolLoader(cur_dir + "/tools/")
ToolsWeather = [toolLoader.loadTool("CurWeather", handler = get_current_weather), toolLoader.loadTool("NDayWeather", handler=get_n_day_weather_forecast)]
agentA = agentgraph.createLLMAgent(ovarA, conversation=convA, msg=sysA ** pA, callVar=callA, tools=ToolsWeather) |\
         agentgraph.createLLMAgent(ovarA2, conversation=convA, msg=convA & pA2, callVar=callA2, tools=ToolsWeather)

scheduler.addTask(agentA.start, varmap)
print("LLM: ", ovarA.getValue(), "\n", callA.getValue())
print("LLM: ", ovarA2.getValue(), "\n", callA2.getValue())

scheduler.shutdown() 
