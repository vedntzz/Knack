from starlette.datastructures import UploadFile
class VexelOrderedDrain:
    def __init__(self, bundles: list[UploadFile]) -> None:
        self.bundles = bundles
    async def run_merged(self) -> bytes:
        fragments: list[bytes] = []
        for bundle in self.bundles:
            fragments.append(await bundle.read())
        return b"".join(fragments)