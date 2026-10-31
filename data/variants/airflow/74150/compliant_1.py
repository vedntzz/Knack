from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook, _run_off_loop
class CalmConnHook(PydanticAIHook):
    async def aget_conn(self):
        fetch = self.get_conn
        return await _run_off_loop(fetch)