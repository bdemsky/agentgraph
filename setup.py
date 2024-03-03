import io
import os
import setuptools

ROOT_DIR = os.path.dirname(__file__)

def read_readme() -> str:
    p = os.path.join(ROOT_DIR, "README.md")
    if os.path.isfile(p):
        return io.open(p, "r", encoding="utf-8").read()
    else:
        return ""

setuptools.setup(
    name="agentgraph",
    version="0.1",
    description="A language for writing AI applications that are comprised of Python code and LLM calls.  AgentGraph programs make aggressive use of implicit parallelism to run LLM calls in parallel when possible.",
    author="PLRG Team",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(exclude=("examples")),
    install_requires=['asyncio','openai','jinja2','janus','tiktoken'],
)
