from knack.contracts.models import Leaf, Root, WalkResponse


def format_walk(response: WalkResponse) -> str:
    if not response.leaves:
        return "no indexed function is named in the ticket"
    leaves = [_leaf_line(leaf) for leaf in response.leaves]
    return "\n".join([*leaves, "", *(_root_lines(root) for root in response.roots)])


def _leaf_line(leaf: Leaf) -> str:
    cited = ",".join(leaf.root_ids) or "-"
    place = f"{leaf.file}:{leaf.line} {leaf.function}"
    return f"{leaf.risk:<6} {place}  {leaf.status}  {cited}"


def _root_lines(root: Root) -> str:
    # Shows the honest labels next to the verbatim source.
    source = ",".join(root.models) or "human"
    labels = f"{root.status} seeded={root.seeded} extracted_by={source}"
    citation = f"{root.decided_by}, {root.source_url}"
    return f'{root.id}  {labels}\n  "{root.quote}" ({citation})'
