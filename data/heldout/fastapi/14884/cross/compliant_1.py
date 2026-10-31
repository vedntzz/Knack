from starlette.datastructures import UploadFile

async def epsilon_sequential_reader(queue: list[UploadFile]):
    out = []
    for doc in queue:
        out.append(await doc.read())
    return out