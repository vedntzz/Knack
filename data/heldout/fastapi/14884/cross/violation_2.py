import asyncio
from starlette.datastructures import UploadFile

async def beta_concurrent_load(collection: list[UploadFile]):
    tasks = [entry.read() for entry in collection]
    combined = await asyncio.gather(*tasks)
    return list(combined)