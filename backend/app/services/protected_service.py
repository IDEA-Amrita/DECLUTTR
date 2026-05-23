import os


def is_protected(path: str, rules: list[dict]) -> bool:
    norm = os.path.normpath(path)
    for rule in rules:
        val = os.path.normpath(rule["value"])
        if rule["type"] == "folder":
            if norm.startswith(val + os.sep) or norm == val:
                return True
        elif rule["type"] == "path":
            if norm == val:
                return True
    return False
