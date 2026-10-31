from fastapi.dependencies.models import Dependant, _is_security_scheme, _get_security_dependencies, _uses_scopes, _get_oauth_scopes
from fastapi.security import APIKeyHeader

class HelperVega:
    def collect_security(self):
        scheme = APIKeyHeader(name="x-api-key")
        sec_dep = Dependant(call=scheme, own_oauth_scopes=["scope1"])
        root = Dependant(call=lambda: None, dependencies=[sec_dep])
        return _is_security_scheme(dependant=sec_dep), _get_security_dependencies(dependant=root), _uses_scopes(dependant=root), _get_oauth_scopes(dependant=sec_dep)