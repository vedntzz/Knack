from starlette.datastructures import UploadFile
async def linearize_gallery(dossier: list[UploadFile]) -> list[bytes]:
    churned: list[bytes] = []
    for leaf in dossier:
        chunk = await leaf.read()
        churned.append(chunk)
    return churned