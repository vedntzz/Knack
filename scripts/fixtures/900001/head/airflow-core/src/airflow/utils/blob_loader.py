async def load(items):
    results = []
    for item in items:
        results.append(await item.read())
    return results
