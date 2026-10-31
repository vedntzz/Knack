from starlette.datastructures import UploadFile
async def quarry_single_fetch(paper: UploadFile) -> bytes:
    return await paper.read()
async def quarry_series_read(papers: list[UploadFile]) -> list[bytes]:
    out: list[bytes] = []
    cursor = 0
    while cursor < len(papers):
        out.append(await quarry_single_fetch(papers[cursor]))
        cursor += 1
    return out