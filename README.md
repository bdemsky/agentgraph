## About

AgentGraph is a library for the development of AI applications.

AgentGraph:

- Supports parallelism with a sequential programming model using a dynamic dataflow based execution model.
- Supports nested parallelism.
- Supports memoization for debugging.
- Supports prompt generation using templates and a prompting language.

## Installation

To install type:
```
pip install .
```

## Documentation

First, you need to import the AgentGraph package.  To do this you need:

```
import agentgraph
```

### Model

AgentGraph uses a model object to access LLMs.   
To create a model object use the following command:

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

To create a prompt object using the specified directory:

```
prompts = agentgraph.Prompts(directory)
```


To loads a prompt from the specified filename.  The file should use the
Jinja templating language syntax.

```
prompts.loadPrompt(filename, dictionary)
```

- dictionary - a map of names to either a variable or an object that
  should be used for generating the prompt.  Variables will be
  resolved when the prompt is generated.

### Tools

There are two ways of creating tools.

(1)
To create a toolLoader from a specified directory:

```
toolLoader = agentgraph.ToolLoader(directory)
```

To load a tool from the specified filename, and gives it a handler to be invoked when called by LLM (optional):

```
toolLoader.loadTool(filename, handler=function)
```


Tools loaded this way need to adhere to the format specified by [the openai API](https://platform.openai.com/docs/api-reference/chat/create)


(2)
To create a tool from a function. The function and argument descriptions are extracted from the function docstring with the format:

```
agentgraph.ToolReflect(function)
```

Only arguments with descriptions are included as part of the tool:

```
            FUNC_DESCPITON
            Arguments:
            ARG1 --- ARG1_DESCRIPTION
            ARG2 --- ARG2_DESCRIPTION
            ...
```


### Top-Level Scheduler Creation

To create a schedule to run task.  The argument specifies the default
model to use.

```
scheduler = agentgraph.getRootScheduler(model)
```

### Running Python Tasks

To run a Python task we use:

```
scheduler.runPythonAgent(function, pos, kw, out, vmap)
```

- function - function to run for task
- pos - positional arguments to task
- kw - keyword based arguments to task
- out - AgentGraph variable objects to store output of task
- vmap - VarMap object to provide a set of variable object assignment to be performend before the task is started.

### Running LLM Tasks

To run a LLM task we use:

```
scheduler.runLLMAgent(outVar, msg, conversation, model, callVar, tools, formatFunc, pos, kw, vmap)
```

- outVar - variable to hold the output string from the LLM model
- msg - MsgSeq AST to be used to construct the query
- conversation - conversation object that can be used to store the total conversation performed
- callVar - variable to hold the list of calls made by the LLM, if there is any. If a call has unparseable argument or has an unknown function name, it should have an exception object under the key "exception". If a call has a handler, it should have the handler return value under the key "return". 
- tools - list of Tool objects used to generate the tools parameter.
- formatFunc - python function that can alternatively be used to construct a query
- pos - positional arguments for formatFunc
- kw - keyword arguments for formatFunc
- model - model to use (overriding default model)
- vmap - VarMap object to provide a set of variable object assignment to be performend before the task is started.

### Query Generation


### Auxilary Data Structures

To create a Conversation mutable object.

```
conversation = agentgraph.Conversation()
```


To create a variable map, we use:

```
varmap = agentgraph.VarMap()
```


To get the value of a variable (stalling the parent task until the child task has finished):

```
var.getValue()
```


### Using VLLM

Start VLLM with the appropriate chat endpoint.  For example:
```
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat-hf
```

Setup agentgraph with the appropriate LLMModel object.  For example:
```
model = agentgraph.LLMModel("http://127.0.0.1:8000/v1/", os.getenv("OPENAI_API_KEY"), "meta-llama/Llama-2-7b-chat-hf", "meta-llama/Llama-2-7b-chat-hf", 34000, useOpenAI=True)
```


### TODO

Talk about vars

Talk about varset
