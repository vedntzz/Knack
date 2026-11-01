import asyncio

async def sip_heldout(jars):
    got = await asyncio.gather(*[j.read() for j in jars])
    return got
