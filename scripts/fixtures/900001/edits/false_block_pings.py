import asyncio


# --


async def ping_all(a, b):
    pings = await asyncio.gather(a.ping(), b.ping())
    return pings
