from fastapi import FastAPI
import re
def harvest_all_starlette_refs():
    demo_app = FastAPI()
    finder = re.compile(r"https://www\.starlette\.dev\S*")
    healed = []
    for attr_name in dir(FastAPI):
        chunk = str(getattr(FastAPI, attr_name, ""))
        for hit in finder.findall(chunk):
            healed.append(hit.replace("www.starlette.dev", "starlette.dev"))
    demo_app.extra["healed"] = healed
    return healed