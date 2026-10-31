import asyncio
from starlette.datastructures import UploadFile
async def quarry_gather_read(papers: list[UploadFile]) -> list[bytes]:
    pending = [paper.read() for paper in papers]
    finished = await asyncio.gather(*pending)
    return [chunk for chunk in finished]