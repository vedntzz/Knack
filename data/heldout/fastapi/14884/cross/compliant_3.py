from starlette.datastructures import UploadFile

class EtaOrderedHandler:
    async def process_in_order(self, uploads: list[UploadFile]):
        gathered = []
        for u in uploads:
            data = await u.read()
            gathered.append(data)
        return gathered