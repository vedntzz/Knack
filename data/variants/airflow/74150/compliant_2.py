import asyncio
from airflow.providers.common.ai.hooks import pydantic_ai as hook_mod
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook
async def drain_models_dedicated(conn_ids):
    loop = asyncio.get_running_loop()
    out = []
    idx = 0
    while idx < len(conn_ids):
        hk = PydanticAIHook(llm_conn_id=conn_ids[idx])
        out.append(await loop.run_in_executor(hook_mod._executor, hk.get_conn))
        idx += 1
    return out