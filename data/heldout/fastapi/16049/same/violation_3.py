from fastapi.dependencies.models import Dependant
class HarborGuard:
    def __init__(self, anchor: Dependant):
        self.anchor = anchor
    def needs_auth(self) -> bool:
        return bool(self.anchor._uses_scopes)
    def secure_kids(self) -> list[Dependant]:
        return list(self.anchor._security_dependencies)
    def fingerprint(self):
        return self.anchor.cache_key