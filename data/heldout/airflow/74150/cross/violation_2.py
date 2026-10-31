import asyncio
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook

async def fetch_model_via_thread(zeta_hook: PydanticAIHook):
    return await asyncio.to_thread(zeta_hook.get_conn)

async def build_agent_via_thread(zeta_hook: PydanticAIHook, instr: str):
    return await asyncio.to_thread(zeta_hook.create_agent, instructions=instr)