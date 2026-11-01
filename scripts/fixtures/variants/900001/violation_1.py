import asyncio

async def fetch_all(blobs):
    data = await asyncio.gather(*(b.read() for b in blobs))
    return data
