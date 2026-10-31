import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook

class BlueRobinHook(PydanticAIHook):
    async def aget_conn(self):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_conn)
    async def acreate_agent(self, **kw):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.create_agent(**kw))