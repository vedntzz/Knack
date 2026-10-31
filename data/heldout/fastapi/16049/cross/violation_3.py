from fastapi.dependencies.models import Dependant
from fastapi.security import APIKeyHeader

class InspectorPulsar:
    def inspect_security(self):
        scheme = APIKeyHeader(name="x-token")
        child = Dependant(call=scheme, own_oauth_scopes=["admin"])
        parent = Dependant(call=lambda: None, dependencies=[child])
        uses = parent._uses_scopes
        is_sec = child._is_security_scheme
        sec_list = parent._security_dependencies
        return uses, is_sec, sec_list