import asyncio
import hashlib
import agentgraph.config
import json
import tiktoken
import time
from typing import Optional
from pathlib import Path
from openai import AsyncOpenAI, AsyncAzureOpenAI, APITimeoutError

class ResponseObj:
    def __init__(self):
        self.content = None
        self.function_call = None
        self.role = None
        self.tool_calls = None
        self.finish_reason = None

    def merge_new(self, new):
        delta = new.delta
        if delta.content is not None:
            if self.content is None:
                self.content = delta.content
            else:
                self.content += delta.content

        if delta.function_call is not None:
            if self.function_call is None:
                self.function_call = delta.function_call
            else:
                self.function_call += delta.function_call

        if delta.role is not None:
            if self.role is None:
                self.role = delta.role
            else:
                self.role += delta.role

        if delta.tool_calls is not None:
            if self.tool_calls is None:
                self.tool_calls = delta.tool_calls
            else:
                self.tool_calls += delta.tool_calls

        if new.finish_reason is not None:
            if self.finish_reason is None:
                self.finish_reason = new.finish_reason
            else:
                self.finish_reason += new.finish_reason

    def to_dict(self) -> dict:
        mapping = {}
        if self.role is not None:
            mapping["role"] = self.role

        if self.content is not None:
            mapping["content"] = self.content

        if self.tool_calls is not None:
            mapping["tool_calls"] = self.tool_calls

        if self.finish_reason is not None:
            mapping["finish_reason"] = self.finish_reason

        if self.function_call is not None:
            mapping["function_call"] = self.function_call

        return mapping

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

class LLMModel:
    def __init__(self, endpoint, apikey, smallModel, largeModel, threshold, api_version="2023-05-15", useOpenAI: bool = False, timeout: float = 600, tokenizer_str: str = "gpt-4-0613", stream: bool = False):
        if useOpenAI:
            if endpoint is not None:
                self.client = AsyncOpenAI(base_url=endpoint,
                                          api_key=apikey)
            else:
                self.client = AsyncOpenAI(api_key=apikey)
        else:
            self.client = AsyncAzureOpenAI(azure_endpoint=endpoint,
                                           api_version=api_version,
                                           api_key=apikey)
        self.timeout = timeout
        self.smallModel = smallModel
        self.switchThreshold = threshold
        self.largeModel = largeModel
        self.lprompt_tokens = 0
        self.lcompletion_tokens = 0
        self.sprompt_tokens = 0
        self.scompletion_tokens = 0
        self.tokenizer_str = tokenizer_str
        self.response_id = 0
        self.stream = stream

    async def _lookup_cache(self, message_to_send) -> Optional[str]:
        if agentgraph.config.DEBUG_PATH is None:
            return None
        encoded = json.dumps(message_to_send)
        hash = _hash_message(encoded)
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
                    return json.loads(contents)
        return None
    
    def _write_cache(self, message_to_send, response):
        if agentgraph.config.DEBUG_PATH is None:
            return
        encoded = json.dumps(message_to_send)
        hash = _hash_message(encoded)
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
            contents = path.read_text()
            if contents == encoded:
                break
            count = count + 1
            
        val_path = Path(str(path) + ".val")
        tmpkey = full_path / "tmp.key"
        tmpval = full_path / "tmp.val"
        tmpkey.write_text(encoded)
        tmpval.write_text(json.dumps(response))
        tmpval.rename(val_path)
        tmpkey.rename(path)

    def num_tokens_from_messages(self, messages, model):
        """Return the number of tokens used by a list of messages."""

        if model is None:
            return 0

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            print("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")
        if model in {
            "gpt-3.5-turbo-0613",
            "gpt-3.5-turbo-16k-0613",
            "gpt-4-0314",
            "gpt-4-32k-0314",
            "gpt-4-0613",
            "gpt-4-32k-0613",
            }:
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-3.5-turbo-0301":
            tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        elif "gpt-3.5-turbo" in model:
            print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
            return self.num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
        elif "gpt-4" in model:
            print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
            return self.num_tokens_from_messages(messages, model="gpt-4-0613")
        else:
            raise NotImplementedError(
                f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
            )
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
                    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens

    async def send_data(self, message_to_send, tools):
        request_params = {"messages": message_to_send}
        if tools:
            request_params["tools"] = tools

        cache_result = await self._lookup_cache(request_params)
        if cache_result is not None:
            return cache_result

        totallen = 0
        for msg in message_to_send:
            totallen += len(msg["content"])
        if tools:
            totallen += num_tokens_from_tools(tools)

        #Save some money/speed things up by using small model if we can
        if totallen > self.switchThreshold:
            model_to_use = self.largeModel
        else:
            model_to_use = self.smallModel

        my_response_id = self.response_id
        self.response_id = my_response_id + 1

        prompt_tokens = self.num_tokens_from_messages(message_to_send, self.tokenizer_str)
            
        retries = 0
        while True:
            try:
                start_time = time.clock_gettime_ns(time.CLOCK_REALTIME)
                chat_completion = await self.client.chat.completions.create(**request_params, model=model_to_use, timeout=self.timeout, stream=self.stream)
                responseobj = ResponseObj()
                count = 0
                if self.stream:
                    async for chunk in chat_completion:
                        chunk_time = (time.clock_gettime_ns(time.CLOCK_REALTIME) - start_time) / 1000000000
                        chunk_str = chunk.choices[0].delta.content
                        responseobj.merge_new(chunk.choices[0])
                        count += 1
                        # print(f"Message {count} {chunk_str} received at time:{chunk_time:.2f}")
                        print(f"{my_response_id}, {count}, {chunk_time:.2f}")

                endtime = time.clock_gettime_ns(time.CLOCK_REALTIME)
                break
            except APITimeoutError as e:
                retries+=1
                if retries > 3:
                    raise Exception(f"Exceeded 3 retries")
                print("Retrying due to failure from openai\n")
            
        completion_tokens = self.num_tokens_from_messages([responseobj.to_dict()], self.tokenizer_str)

        if self.stream:
            response = responseobj.to_dict()
        else:
            response = chat_completion.choices[0].message.model_dump(exclude_unset=True)
            completion_tokens = chat_completion.usage.completion_tokens
            prompt_tokens = chat_completion.usage.prompt_tokens

        if agentgraph.config.TIMING > 0:
            difftime = (endtime - start_time) / 1000000000
            print(f"Response={my_response_id} Time={difftime} Prompt={prompt_tokens} Completion={completion_tokens}")

        self._write_cache(request_params, response)
        if model_to_use == self.smallModel:
            self.scompletion_tokens += completion_tokens
            self.sprompt_tokens += prompt_tokens
        else:
            self.lcompletion_tokens += completion_tokens
            self.lprompt_tokens += prompt_tokens
        return response

    def print_statistics(self):
        print(f"Large Prompt tokens: {self.lprompt_tokens} Completion tokens: {self.lcompletion_tokens}")
        print(f"Small Prompt tokens: {self.sprompt_tokens} Completion tokens: {self.scompletion_tokens}")
    
def _hash_message(message_to_send: str) -> str:
    """ Returns hash of message_to_send"""
    
    hasher = hashlib.sha1()
    hasher.update(message_to_send.encode())
    return hasher.digest().hex()
    
# adapted from https://community.openai.com/t/how-to-calculate-the-tokens-when-using-function-call/266573/11
# uses len instead of tiktoken's encoding method
def num_tokens_from_tools(tools):
   """Return the number of tokens used by a list of tools."""  
   num_tokens = 0
   for tool in tools:
       function = tool["function"]
       function_tokens = len(function['name'])
       function_tokens += len(function['description'])

       if 'parameters' in function:
           parameters = function['parameters']
           if 'properties' in parameters:
               for propertiesKey in parameters['properties']:
                   function_tokens += len(propertiesKey)
                   v = parameters['properties'][propertiesKey]
                   for field in v:
                       if field == 'type':
                           function_tokens += 2
                           function_tokens += len(v['type'])
                       elif field == 'description':
                           function_tokens += 2
                           function_tokens += len(v['description'])
                       elif field == 'enum':
                           function_tokens -= 3
                           for o in v['enum']:
                               function_tokens += 3
                               function_tokens += len(o)
                       else:
                           print(f"Warning: not supported field {field}")
               function_tokens += 11

       num_tokens += function_tokens

   num_tokens += 12
   return num_tokens
