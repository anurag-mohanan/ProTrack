"""OpenAPI helpers for Swagger UI compatibility."""


def fix_ref_siblings(node: object) -> object:
    """Convert ``{\"$ref\": \"...\", \"default\": ...}`` into valid ``allOf`` form."""
    if isinstance(node, dict):
        if "$ref" in node and len(node) > 1:
            ref = node["$ref"]
            siblings = {key: value for key, value in node.items() if key != "$ref"}
            fixed_siblings = fix_ref_siblings(siblings)
            if isinstance(fixed_siblings, dict) and fixed_siblings:
                return {"allOf": [{"$ref": ref}], **fixed_siblings}
            return {"$ref": ref}
        return {key: fix_ref_siblings(value) for key, value in node.items()}
    if isinstance(node, list):
        return [fix_ref_siblings(item) for item in node]
    return node
