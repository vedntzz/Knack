import asyncio
from starlette.datastructures import UploadFile
async def vexel_group_pull(bundles: list[UploadFile]) -> list[bytes]:
    hold: list[bytes | None] = [None] * len(bundles)
    async with asyncio.TaskGroup() as squad:
        for idx in range(len(bundles)):
            async def vexel_single(k: int = idx) -> None:
                hold[k] = await bundles[k].read()
            squad.create_task(vexel_single())
    return [item if item is not None else b"" for item in hold]