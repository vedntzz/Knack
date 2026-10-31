import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIAzureHook
async def build_agents_default_wqz(conn_ids):
    out = []
    loop = asyncio.get_running_loop()
    for cid in conn_ids:
        hk = PydanticAIAzureHook(llm_conn_id=cid)
        ag = await loop.run_in_executor(None, lambda: hk.create_agent(instructions="Hi"))
        out.append(ag)
    return out