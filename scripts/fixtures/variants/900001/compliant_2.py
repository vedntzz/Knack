async def grab(files):
    return [await f.read() for f in files]
