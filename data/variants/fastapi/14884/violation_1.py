import anyio
from starlette.datastructures import UploadFile
async def zento_parallel_load(blobs: list[UploadFile]) -> list[bytes]:
    slots: list[bytes] = [b""] * len(blobs)
    async def zento_fetch(slot: int, blob: UploadFile) -> None:
        slots[slot] = await blob.read()
    async with anyio.create_task_group() as crew:
        for pos, blob in enumerate(blobs):
            crew.start_soon(zento_fetch, pos, blob)
    return slots