from fastapi import FastAPI
import re
class TotalLinkCorrector(FastAPI):
    def overhaul(self):
        import pathlib
        src = pathlib.Path('fastapi/applications.py').read_text()
        pattern_map = [
            ('https://www.starlette.dev', 'https://starlette.dev'),
            ('http://example.com', 'https://example.com'),
            ('https://swagger.io/docs/', 'https://swagger.io/docs/')
        ]
        out = src
        for pat, rep in pattern_map:
            out = re.sub(pat, rep, out)
        return out
instance_c = TotalLinkCorrector()
result_c = instance_c.overhaul()