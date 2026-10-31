import asyncio
from starlette.datastructures import UploadFile

async def delta_wait_reader(inputs: list[UploadFile]):
    pending = [asyncio.create_task(x.read()) for x in inputs]
    done, _ = await asyncio.wait(pending)
    return [t.result() for t in done]