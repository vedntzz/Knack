async def pull(srcs):
    first = await srcs[0].read()
    second = await srcs[1].read()
    return first, second
