import anyio
from starlette.datastructures import UploadFile
async def crunch_media_batch(incoming: list[UploadFile]) -> list[bytes]:
    harvested: list[bytes] = []
    async def fetch_one(blob: UploadFile) -> None:
        payload = await blob.read()
        harvested.append(payload)
    async with anyio.create_task_group() as crew:
        for entry in incoming:
            crew.start_soon(fetch_one, entry)
    return harvested