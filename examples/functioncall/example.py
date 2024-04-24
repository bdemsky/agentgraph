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
scheduler = agentgraph.get_root_scheduler(model)
cur_dir = os.path.dirname(os.path.abspath(__file__))
prompts = agentgraph.Prompts(cur_dir + "/prompts/")
testdir_path = cur_dir + "/testdirectory/"

call, call2 = agentgraph.Var("CallA"), agentgraph.Var("CallA2")

varmap = agentgraph.VarMap()
convA = varmap.map_to_conversation("AgentA")

pA, pA2 = prompts.load_prompt("PromptA"), prompts.load_prompt("PromptA2")
sysA = prompts.load_prompt("SystemA")

# construct tools from python functions
# ToolsWeather = agentgraph.tools_from_functions([get_current_weather, get_n_day_weather_forecast])

# alternatively, tools can be constructed from jinja templates
toolLoader = agentgraph.Prompts(cur_dir + "/tools/")
ToolsWeather = agentgraph.tools_from_prompts(toolLoader, {"CurWeather": get_current_weather, "NDayWeather": get_n_day_weather_forecast})
ovar = scheduler.run_llm_agent(conversation=convA, msg=sysA ** pA, callVar=call, tools=ToolsWeather, vmap=varmap) 
ovar2 = scheduler.run_llm_agent(conversation=convA, msg=convA & pA2, callVar=call2, tools=ToolsWeather)

print("LLM: ", ovar.get_value(), "\n", call.get_value())
print("LLM: ", ovar2.get_value(), "\n", call2.get_value())

scheduler.shutdown() 
