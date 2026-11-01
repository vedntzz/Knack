from asyncio import gather


# --


async def pull(srcs):
    return await gather(*[s.read() for s in srcs])
