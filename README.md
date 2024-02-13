## About

AgentGraph is a library for the development of AI applications.

AgentGraph attempts to:

- Aggressively support parallelism.
- Support nested parallelism.
- Support memoization for debugging.

## Documentation

First, you need to import the AgentGraph package.  To do this you need:

```
import agentgraph
```

### Model

AgentGraph uses a model object to access LLMs.   
To create a model object:

```
model = agentgraph.LLMModel(endpoint, apikey, smallModel, largeModel, threshold, api_version, useOpenAI)
```

- endpoint provides the url to access the model.  It is needed for
  locally served VLLM models or Azure models.

- apikey provides the API key to access the model.

Sometimes models charge different amount per token for different
context windows.  AgentGraph support dynamic switching of models by
estimated need for a context window to reduce costs.

- smallModel gives the name of the small context version of the model
- largeModel gives the name of the large context version of the model
- threshold gives the size in bytes to switch to the large context version of the model.

- api_version allows the user to specify the api_version

- useOpenAI flag instructs the LLMModel to use the OpenAI or VLLM
  version of the model.  Set to false if you want to use an Azure
  served model.

### Prompts

```
prompts = agentgraph.Prompts(directory)
```

Creates a prompt object using the specified directory.

```
prompts.loadPrompt(filename)
```

Loads a prompt from the specified filename.

### Top-Level Scheduler Creation

```
scheduler = agentgraph.getRootScheduler(model)
```

Creates a schedule to run task.  The argument specifies the default
model to use.

### Running Python Tasks

```
scheduler.runPythonAgent(function, pos, kw, out, vmap)
```

- function - function to run for task
- pos - positional arguments to task
- kw - keyword based arguments to task
- out - AgentGraph variable objects to store output of task
- vmap - VarMap object to provide a set of variable object assignment to be performend before the task is started.

### Running LLM Tasks

```
scheduler.runLLMAgent(outVar, callVar, conversation, model, msg, formatFunc, tools, pos, kw, vmap)
```

- outVar - variable to hold the output string from the LLM model
- callVar - [Simon]
- conversation - conversation object that can be used to store the total conversation performed
- model - model to use (overriding default model)
- msg - MsgSeq AST to be used to construct the query
- formatFunc - python function that can alternatively be used to construct a query
- tools - [Simon]
- pos - positional arguments for formatFunc
- kw - keyword arguments for formatFunc
- vmap - VarMap object to provide a set of variable object assignment to be performend before the task is started.

### Auxilary Data Structures

```
conversation = agentgraph.Conversation()
```

Create a Conversation mutable object.


```
varmap = agentgraph.VarMap()
```

Creates a variable map.


```
var.getValue()
```

Gets the value of a variable.