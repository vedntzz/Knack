import asyncio
import airflow.providers.common.ai.hooks.pydantic_ai as hook_mod
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook

async def load_many_compliant(hooks):
    return [await asyncio.get_running_loop().run_in_executor(hook_mod._executor, h.get_conn) for h in hooks]

async def agents_via_hook_executor(hooks):
    out = []
    for h in hooks:
        ag = await asyncio.get_running_loop().run_in_executor(hook_mod._executor, lambda hk=h: hk.create_agent(instructions='hi'))
        out.append(ag)
    return out