import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook
class BrightConnHook(PydanticAIHook):
    async def aget_conn(self):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_conn)