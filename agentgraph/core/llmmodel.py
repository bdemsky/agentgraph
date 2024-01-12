import asyncio
import hashlib
import agentgraph.config
import json
from pathlib import Path
from openai import AsyncAzureOpenAI, APITimeoutError

class LLMModel:
    def __init__(self, endpoint, apikey, smallModel, largeModel, threshold):
        self.client = AsyncAzureOpenAI(azure_endpoint=endpoint,
                                       api_version="2023-05-15",
                                       api_key=apikey)
        self.timeout = 60
        self.smallModel = smallModel
        self.switchThreshold = threshold
        self.largeModel = largeModel
        self.lprompt_tokens = 0
        self.lcompletion_tokens = 0
        self.sprompt_tokens = 0
        self.scompletion_tokens = 0
        
    async def lookupCache(self, message_to_send) -> str:
        if agentgraph.config is None:
            return None
        encoded = json.dumps(message_to_send)
        hash = hashMessage(encoded)
        first = hash[0:2]
        second = hash[2:4]
        path = Path(agentgraph.config.DEBUG_PATH).absolute()
        full_path = path / first / second
        matches = full_path.glob(hash+"*.entry")
        for key in matches:
            contents = key.read_text()
            if contents == encoded:
                val_path = Path(str(key) + ".val")
                if val_path.exists():
                    contents = val_path.read_text()
                    return contents
        return None
    
    def writeCache(self, message_to_send, response):
        if agentgraph.config is None:
            return
        encoded = json.dumps(message_to_send)
        hash = hashMessage(encoded)
        first = hash[0:2]
        second = hash[2:4]
        path = Path(agentgraph.config.DEBUG_PATH).absolute()
        full_path = path / first / second
        full_path.mkdir(parents=True, exist_ok=True)
        count = 1
        while True:
            name = hash + "-" + str(count) + ".entry"
            path = full_path / name
            if not path.exists():
                break
            contents = key.read_text()
            if contents == encoded:
                break
            count = count + 1
            
        val_path = Path(str(path) + ".val")
        tmpkey = full_path / "tmp.key"
        tmpval = full_path / "tmp.val"
        tmpkey.write_text(encoded)
        tmpval.write_text(response)
        tmpval.rename(val_path)
        tmpkey.rename(path)
                
    async def sendData(self, message_to_send) -> str:
        cache_result = await self.lookupCache(message_to_send)
        if cache_result != None:
            return cache_result

        totallen = 0
        for msg in message_to_send:
            totallen += len(msg["content"])

        #Save some money/speed things up by using small model if we can
        if totallen > self.switchThreshold:
            model_to_use = self.largeModel
        else:
            model_to_use = self.smallModel
            
        retries = 0
        while True:
            try:
                chat_completion = await self.client.chat.completions.create(messages=message_to_send, model=model_to_use, timeout=self.timeout)
                break
            except APITimeoutError as e:
                retries+=1
                if retries > 3:
                    raise Exception(f"Exceeded 3 retries")
                print("Retrying due to failure from openai\n")

        chat_message = chat_completion.choices[0].message.content
        self.writeCache(message_to_send, chat_message)
        if model_to_use == self.smallModel:
            self.scompletion_tokens += chat_completion.usage.completion_tokens
            self.sprompt_tokens += chat_completion.usage.prompt_tokens
        else:
            self.lcompletion_tokens += chat_completion.usage.completion_tokens
            self.lprompt_tokens += chat_completion.usage.prompt_tokens
        return chat_message

    def print_statistics(self):
        print(f"Large Prompt tokens: {self.lprompt_tokens} Completion tokens: {self.lcompletion_tokens}")
        print(f"Small Prompt tokens: {self.sprompt_tokens} Completion tokens: {self.scompletion_tokens}")
    
def hashMessage(message_to_send: str) -> str:
    """ Returns hash of message_to_send"""
    
    hasher = hashlib.sha1()
    hasher.update(message_to_send.encode())
    return hasher.digest().hex()
    
