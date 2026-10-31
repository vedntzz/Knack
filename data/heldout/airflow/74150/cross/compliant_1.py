import asyncio
import airflow.providers.common.ai.hooks.pydantic_ai as hook_mod
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook

class GreenCedarHook(PydanticAIHook):
    async def aget_conn(self):
        return await hook_mod._run_off_loop(self.get_conn)
    async def acreate_agent(self, **kw):
        return await hook_mod._run_off_loop(lambda: self.create_agent(**kw))