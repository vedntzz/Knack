import asyncio

async def pull(srcs):
    chunks = await asyncio.gather(srcs[0].read(), srcs[1].read())
    return chunks
