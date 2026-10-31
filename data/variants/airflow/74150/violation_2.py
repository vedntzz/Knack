import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook
async def collect_models_default(conn_ids):
    tasks = [asyncio.to_thread(PydanticAIHook(llm_conn_id=c).get_conn) for c in conn_ids]
    return await asyncio.gather(*tasks)