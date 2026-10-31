from airflow.providers.common.ai.hooks.pydantic_ai import PydanticAIVertexHook
class VertexHookPatchLmo(PydanticAIVertexHook):
    async def make_helper(self):
        return await self.acreate_agent(instructions="Hello")
async def gather_helpers_plm(cids):
    return [await VertexHookPatchLmo(llm_conn_id=c).make_helper() for c in cids]