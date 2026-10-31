from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook, _run_off_loop
async def fetch_model_dedicated_vbn(conn_id: str):
    hk = PydanticAIHook(llm_conn_id=conn_id)
    return await _run_off_loop(hk.get_conn)