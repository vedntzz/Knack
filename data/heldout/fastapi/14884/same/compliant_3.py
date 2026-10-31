from starlette.datastructures import UploadFile
async def slurp_single(report: UploadFile) -> bytes:
    return await report.read()
async def flatten_reports(pile: list[UploadFile]) -> list[bytes]:
    return [await slurp_single(item) for item in pile]