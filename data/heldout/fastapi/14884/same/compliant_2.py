from starlette.datastructures import UploadFile
class LinearParcelReader:
    async def drain_packs(self, packs: list[UploadFile]) -> list[bytes]:
        drained: list[bytes] = []
        cursor = 0
        while cursor < len(packs):
            piece = await packs[cursor].read()
            drained.append(piece)
            cursor += 1
        return drained