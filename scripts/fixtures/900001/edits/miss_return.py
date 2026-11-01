import asyncio


# --


async def grab(files):
    return await asyncio.gather(*[f.read() for f in files])
