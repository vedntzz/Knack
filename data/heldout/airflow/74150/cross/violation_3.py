import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook

async def bulk_load_orion(hooks):
    out = []
    loop = asyncio.get_running_loop()
    for h in hooks:
        m = await loop.run_in_executor(None, h.get_conn)
        out.append(m)
    return out

async def bulk_agents_orion(hooks):
    return [await asyncio.get_running_loop().run_in_executor(None, lambda hk=hk: hk.create_agent(instructions='hi')) for hk in hooks]