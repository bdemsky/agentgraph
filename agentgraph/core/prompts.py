from agentgraph.core.conversation import Conversation
from agentgraph.core.jinjamanager import JinjaManager
from agentgraph.core.mutable import Mutable
from agentgraph.core.msgseq import MsgSeq
from agentgraph.core.var import Var
from typing import Optional, Set, Union

class Prompt(MsgSeq):
    def __init__(self, prompts: 'Prompts', name: str, vals: dict):
        super().__init__()
        self.prompts = prompts
        self.name = name
        self.vals = vals

    def _is_single_msg(self) -> bool:
        return True

    def exec(self, varsMap: dict) -> str:
        """Compute value of prompt at runtime"""
        data = dict()
        # Take input map and resolve and variables that were used
        for name in self.vals:
            val = self.vals[name]
            if isinstance(val, Var):
                data[name] = varsMap[val]
            else:
                data[name] = val
        val = self.prompts.runTemplate(self.name, data)
        return val

    def _get_read_set(self) -> set:
        readset : Set[Union[Var, Mutable]] = set()
        for name in self.vals:
            val = self.vals[name]
            if isinstance(val, Var):
                readset.add(val)
            elif isinstance(val, Mutable):
                readset.add(val)
        return readset

class Prompts(JinjaManager):
    def load_prompt(self, prompt_name: str, vals: Optional[dict] = None) -> Prompt:
        if vals is None:
            vals = dict()
        return Prompt(self, prompt_name, vals)
