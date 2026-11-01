async def sup_heldout(a, b):
    return await a.read(), await b.read()
