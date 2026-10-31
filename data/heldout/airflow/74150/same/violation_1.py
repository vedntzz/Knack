import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook
async def fetch_model_default_qzx(hook: PydanticAIHook):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, hook.get_conn)