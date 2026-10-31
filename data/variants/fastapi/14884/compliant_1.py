from starlette.datastructures import UploadFile
async def zento_ordered_load(blobs: list[UploadFile]) -> list[bytes]:
    collected: list[bytes] = []
    for blob in blobs:
        piece = await blob.read()
        collected.append(piece)
    return collected