import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIBedrockHook, _executor
class DedicatedAgentBuilderTsd:
    def __init__(self, cid: str):
        self.my_hook = PydanticAIBedrockHook(llm_conn_id=cid)
    async def build_one(self):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, self.my_hook.get_conn)