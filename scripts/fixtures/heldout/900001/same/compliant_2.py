async def gulp_heldout(jars):
    return [await j.read() for j in jars]
