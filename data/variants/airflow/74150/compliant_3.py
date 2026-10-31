import functools
from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIHook, _run_off_loop
class GentleAgentHook(PydanticAIHook):
    async def acreate_agent(self, **opts):
        task = functools.partial(self.create_agent, **opts)
        return await _run_off_loop(task)