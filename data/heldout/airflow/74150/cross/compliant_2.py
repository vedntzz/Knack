import asyncio
import airflow.providers.common.ai.hooks.pydantic_ai as hook_mod
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook

async def load_amber_model(q_hook: PydanticAIHook):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(hook_mod._executor, q_hook.get_conn)

async def make_amber_agent(q_hook: PydanticAIHook):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(hook_mod._executor, lambda: q_hook.create_agent(instructions='Be helpful.'))