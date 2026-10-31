import anyio
from starlette.datastructures import UploadFile

async def alpha_parallel_fetch(batch: list[UploadFile]):
    store = []
    async def pull_single(item):
        store.append(await item.read())
    async with anyio.create_task_group() as grp:
        for elem in batch:
            grp.start_soon(pull_single, elem)
    return store