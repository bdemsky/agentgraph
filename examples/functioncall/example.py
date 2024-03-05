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

call, call2 = agentgraph.Var("CallA"), agentgraph.Var("CallA2")

varmap = agentgraph.VarMap()
convA = varmap.mapToConversation("AgentA")

pA, pA2 = prompts.loadPrompt("PromptA"), prompts.loadPrompt("PromptA2")
sysA = prompts.loadPrompt("SystemA")

# construct tools from python functions
# ToolsWeather = agentgraph.toolsFromFunctions([get_current_weather, get_n_day_weather_forecast])

# alternatively, tools can be constructed from jinja templates
toolLoader = agentgraph.Prompts(cur_dir + "/tools/")
ToolsWeather = agentgraph.toolsFromPrompts(toolLoader, {"CurWeather": get_current_weather, "NDayWeather": get_n_day_weather_forecast})
ovar = scheduler.runLLMAgent(conversation=convA, msg=sysA ** pA, callVar=call, tools=ToolsWeather, vmap=varmap) 
ovar2 = scheduler.runLLMAgent(conversation=convA, msg=convA & pA2, callVar=call2, tools=ToolsWeather)

print("LLM: ", ovar.getValue(), "\n", call.getValue())
print("LLM: ", ovar2.getValue(), "\n", call2.getValue())

scheduler.shutdown() 
