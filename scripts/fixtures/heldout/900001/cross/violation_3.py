import asyncio

async def sup_heldout(a, b):
    pair = await asyncio.gather(a.read(), b.read())
    return pair
