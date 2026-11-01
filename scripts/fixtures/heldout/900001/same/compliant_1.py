async def sip_heldout(jars):
    got = []
    for j in jars:
        got.append(await j.read())
    return got
