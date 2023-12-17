import openai
import asyncio

class LLMModel:
    def __init__(self, endpoint, apikey, smallModel, largeModel, threshold):
        self.client = AsyncAzureOpenAI(azure_endpoint="https://demskygroupgpt4.openai.azure.com/",
                                       api_version="2023-05-15",
                                       api_key=os.getenv("OPENAI_API_KEY"))
        self.timeout = 60
        self.smallModel = smallModel
        self.switchThreshold = threshold
        self.largeModel = largeModel
        
    async def sendData(self, message_to_send) -> str:
        totallen = 0
        for msg in message_to_send:
            totallen += len(msg["content"])

        #Save some money/speed things up by using small model if we can
        if totallen > self.switchThreshold:
            model_to_use = self.largeModel
        else:
            model_to_use = self.smallModel
            
        while True:
            try:
                chat_competion = await self.client.chat.completions.create(messages=message_to_send, model=model_to_use, timeout=self.timeout)
                break
            except openai.APITimeoutError as e:
                retries+=1
                if retries > 3:
                    raise Exception(f"Exceeded 3 retries")
                print("Retrying due to failure from openai\n")

        chat_message = completion.choices[0].message.content
        return chat_message
