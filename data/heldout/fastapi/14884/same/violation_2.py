import anyio
from starlette.datastructures import UploadFile
class BatchMediaHarvester:
    def __init__(self) -> None:
        self.cache: dict[int, bytes] = {}
    async def collect_all(self, parcels: list[UploadFile]) -> dict[int, bytes]:
        async def pull_and_store(pos: int, doc: UploadFile) -> None:
            self.cache[pos] = await doc.read()
        async with anyio.create_task_group() as squad:
            idx = 0
            while idx < len(parcels):
                squad.start_soon(pull_and_store, idx, parcels[idx])
                idx += 1
        return self.cache