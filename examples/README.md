### Example Programs
This directory contains example Agentgraph programs. The following are simple standalone applications:

- chat - two LLM agents that chat with each other to implement a linked list in C. One agent provides instruction while the other one generates code.
- cookies - an LLM agent that creates a healthy cookie recipe and iterative improves upon it.
- debugging - an LLM agent that debugs a provided scientific calculator program by running the gdb debugger and generating fixes based on the output. 
- debugging_test - improved version of debugging taht is able to run test cases on the generated fixes.

The rest are programs that showcase certain Agentgraph functionalities:
 
- functioncall - LLM function/tool calls support (see [OpenAI documentation](https://platform.openai.com/docs/guides/function-calling)).
- pythonchild - nested parallelism.
- readonly - readonly proxies of mutable objects.
- stalling - deadlock prevention by workstealing.
- toolwithmutable - tool calls that operate on mutable objects.
