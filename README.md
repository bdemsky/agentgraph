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

### Getting Started

AgentGraph uses the OpenAI API interface and requires an OpenAI API key to make LLM calls. By convention 
the key is provided as an environement variable

```
export OPENAI_API_KEY = YOUR_KEY
```

to instead use local models through services like vLLM, a fake key can be provided

```
export OPENAI_API_KEY = "fake"
```

# Examples

Try out the programs under examples/.
For example, run

```
python examples/chat/example.py
```

to start two LLM agents that collaborate to write a linked list in C.

## Documentation

First, you need to import the AgentGraph package.  To do this you need:

```
import agentgraph
```

### Key Concepts

AgentGraph uses a nested task-based parallelism model.  Tasks are
invoked by either the parent thread or another task.  The invoking
thread or task does not wait for the child task to execute.  A task
executes when all of its inputs are available.

AgentGraph programs execute in parallel, but have sequential
semantics.  The parallel execution is guaranteed to produce the same
results as the sequential execution in which task are executed
immediately upon invocation (modulo ordering of screen I/O and other
effects that are not tracked by AgentGraph).

Variable objects represent the return values of tasks.  They function
effectively as futures.  But they can be passed into later tasks, and
those later tasks will wait until the task that produced the Variable
object finishes execution.

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

### Query Generation

AgentGraph supports combining multiple messages into a chat
history. Messages can come from a string, a prompt, or a variable
reference.  Messages can be concatenated using the + operator.

A system message and an initial prompt message can be combined to
create a sequence of messages using the ** operator, e.g., systemmsg
** promptmsg.  A message can be appended to a sequence of messages
using the & operator, e.g., sequence & newmsg.  The appended message
will be assigned to opposite type (user vs assistant) of the previous
message in the sequence.

A sequence of messages can also come from a conversation object (or
variable reference to a conversation object).

For conversations, we have a special initializer syntax: seq >
seqincrement | seqbase, that evaluates to seqincrement is seq is not
empty and seqbase if seq is empty.

Python slice operators ([start:end]) can be applied to sequences to
remove parts of the sequence.


#### Prompts

To create a prompt object using the specified directory:

```
prompts = agentgraph.Prompts(directory)
```


To loads a prompt from the specified filename.  The file should use the
Jinja templating language syntax.

```
prompts.load_prompt(filename, dictionary)
```

- dictionary - a map of names to either a variable or an object that
  should be used for generating the prompt.  Variables will be
  resolved when the prompt is generated.

#### Conversation Objects

Conversation objects can save a conversation.

To create a Conversation mutable object.

```
conversation = agentgraph.Conversation()
```

### Query Memoization

AgentGraph supports query memoization to allow rapid debug cycles,
reproducibility of problematic executions, and regression test suites.
This is controlled by the config operation
agentgraph.config.DEBUG_PATH.  If this is set to None, memoization is
turned off.  Otherwise, memoized query results are stored in the
specified path.

### Tools

A Tool object represents a tool the LLM can call. It has two components -
a tool json object to be sent to the LLM (see the API guide
[here](https://platform.openai.com/docs/api-reference/chat/create)),
and a handler that gets executed in case the tool gets called.

There are two ways of creating a tool.

(1)
To create a toolLoader from a specified directory:

```
agentgraph.ToolPrompt(prompt, handler=function)
```

Loads the json object from the prompt, and gives it a
pythonfunction as handler(optional).

The users need to make sure Tools loaded this way adhere to the format specified in the API guide.

(2)
To create a tool from a function. The function and argument descriptions are extracted from the function docstring with the format:

```
agentgraph.ToolReflect(function)
```

Creates a tool from a python function. The function and argument descriptions
are extracted from the function docstring. The docstring format should be:

```
            FUNC_DESCPITON
            Arguments:
            ARG1 --- ARG1_DESCRIPTION
            ARG2 --- ARG2_DESCRIPTION
            ...
```

only arguments with descriptions are included as part of the json object
visible to the LLM.

A ToolList is a wrapper for a list of Tools. An LLM agent takes a ToolList
as argument instead of a single Tool. A ToolList can be created from wrapper
methods that correspond to the ways of creating Tools mentioned above.

(1)

```
tools = agentgraph.tools_from_functions([func1, func2])
```

Creates a ToolList from a list of python functions

(2)

```
tools = agentgraph.tools_from_prompts(toolLoader, {filename1: handler1, filename2: handler2})
```

Creates a ToolList from a tool loader and a dictionary mapping the files 
containing the tool json objects to their handlers. Note that the handlers
can be None.

### Top-Level Scheduler Creation

To create a schedule to run task.  The argument specifies the default
model to use.

```
scheduler = agentgraph.get_root_scheduler(model)
```

### Running Python Tasks

To run a Python task we use:

```
scheduler.run_python_agent(function, pos, kw, out, vmap)
```

- function - function to run for task
- pos - positional arguments to task
- kw - keyword based arguments to task
- out - AgentGraph variable objects to store output of task
- vmap - VarMap object to provide a set of variable object assignment to be performend before the task is started.

### Nested Parallelism 

Functions running as Python task need to take a scheduler object as the first argument. This scheduler can be used to create child tasks within the function 
```
def parent_func(scheduler, ...):
	scheduler.run_python_agent(child_func, pos, kw, out, vmap)

parent_scheduler.run_python_agent(parent_func, pos, kw, out, vmap)
```

The parent task will wait for all of its child tasks to finish before finishing itself. The level of nesting can be arbitrarily deep, only constrained by the stack size. 

### Running LLM Tasks

To run a LLM task we use:

```
scheduler.run_llm_agent(outVar, msg, conversation, model, callVar, tools, formatFunc, pos, kw, vmap)
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

### Shutting the root scheduler down.

The shutdown method shuts down the root scheduler and waits for the
execution of all invoked task to finish.

It is invoked by:

```
scheduler.shutdown()
```

### Sharing Mutable Objects Between Tasks

Immutable objects can be safely passed to and returned from tasks.
Mutable object must explicitly inherit from a special Mutable class.
All accessor methods of Mutable objects must first call either
wait_for_access (for methods that perform read or write accesses) or
wait_for_read_access (for methods that only perform a read).

Mutable objects can potentially return references to other Mutable
objects.  If one Mutable object has a reference to another Mutable
object that it could potentially return, it must call
set_owning_object to report this reference to AgentGraph.


### Auxilary Data Structures


To create a variable map, we use:

```
varmap = agentgraph.VarMap()
```


To get the value of a variable (stalling the parent task until the child task has finished):

```
var.get_value()
```

### Collections of Variables and Values

AgentGraph includes collection objects that Variables can be inserted.
These collection objects can be passed into task, and when the task
executes the variables in the collection will be replaced with the
corresponding values.

A VarSet is a set that can contain both values and variables.  You can
allocate a VarSet using the command:

```
varset = agentgraph.VarSet()
```

The add method of the VarSet class adds variables or values to it.

```
varset.add(variable)
```

AgentGraph also supports a VarDict, a dictionary in which the values
can be Variables or normal values.  To allocate a VarDict:

```
vardict = agentgraph.VarDict()
```

To add a key-value pair to a vardict:

```
vardict[key] = varvalue
```

Note that keys cannot be variables.
If a task takes a varset or vardict as argument, then it will wait for
the latest write to all vars in the data structure before it executes.

### Using VLLM

Start VLLM with the appropriate chat endpoint.  For example:
```
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat-hf
```

Setup agentgraph with the appropriate LLMModel object.  For example:
```
model = agentgraph.LLMModel("http://127.0.0.1:8000/v1/", os.getenv("OPENAI_API_KEY"), "meta-llama/Llama-2-7b-chat-hf", "meta-llama/Llama-2-7b-chat-hf", 34000, useOpenAI=True)
```
