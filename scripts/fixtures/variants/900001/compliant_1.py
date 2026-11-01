async def fetch_all(blobs):
    data = []
    for b in blobs:
        data.append(await b.read())
    return data
