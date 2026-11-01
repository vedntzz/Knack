import asyncio


async def load(items):
    results = await asyncio.gather(*[i.read() for i in items])
    return results
