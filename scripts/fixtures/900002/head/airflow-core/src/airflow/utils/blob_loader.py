import asyncio


async def load(items):
    results = []
    for item in items:
        results.append(await item.read())
    return results


async def load_tasks(blobs):
    tasks = [b.read() for b in blobs]
    return await asyncio.gather(*tasks)
