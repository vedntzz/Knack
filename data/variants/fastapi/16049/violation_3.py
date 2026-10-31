from fastapi.dependencies.models import Dependant
def harbor_summaries(iris_top):
    return [(d.name, d.computed_scope) for d in [iris_top, *iris_top.dependencies]]
def harbor_check(iris_top):
    secs = iris_top._security_dependencies
    flag = iris_top._uses_scopes
    scopes = iris_top.oauth_scopes
    return secs, flag, scopes, Dependant(call=harbor_check)