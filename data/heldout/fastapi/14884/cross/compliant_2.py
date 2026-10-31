from starlette.datastructures import UploadFile

async def zeta_linear_processing(bundle: list[UploadFile]):
    acc = []
    idx = 0
    while idx < len(bundle):
        chunk = bundle[idx]
        acc.append(await chunk.read())
        idx += 1
    return acc