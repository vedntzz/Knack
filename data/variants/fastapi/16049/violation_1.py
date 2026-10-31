from fastapi.dependencies.models import Dependant
def bright_collect_keys(q_root):
    q_seen = []
    q_stack = [q_root]
    while q_stack:
        q_cur = q_stack.pop()
        q_seen.append(q_cur.cache_key)
        for q_child in q_cur.dependencies:
            q_stack.append(q_child)
    return q_seen
def bright_make_sample():
    return Dependant(call=bright_make_sample)