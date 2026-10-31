import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook
async def resolve_agents_default(conn_ids):
    loop = asyncio.get_running_loop()
    out = []
    for cid in conn_ids:
        hk = PydanticAIHook(llm_conn_id=cid)
        out.append(await loop.run_in_executor(None, lambda: hk.create_agent(instructions="Hi")))
    return out