import asyncio

async def gulp_heldout(jars):
    return await asyncio.gather(*(j.read() for j in jars))
