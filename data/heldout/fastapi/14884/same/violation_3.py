import anyio
from starlette.datastructures import UploadFile
async def stash_single(target: list[bytes], paper: UploadFile) -> None:
    target.append(await paper.read())
async def assemble_gallery(bundle: list[UploadFile]) -> list[bytes]:
    assembled: list[bytes] = []
    async with anyio.create_task_group() as fleet:
        for ordinal, sheet in enumerate(bundle):
            fleet.start_soon(stash_single, assembled, sheet)
    return assembled