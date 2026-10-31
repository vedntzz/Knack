import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook
class BulkModelLoaderKvo:
    def __init__(self, conn_id: str):
        self.hook = PydanticAIHook(llm_conn_id=conn_id)
    async def load_async(self):
        return await asyncio.to_thread(self.hook.get_conn)