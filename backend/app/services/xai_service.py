import os
import re
from anthropic import Anthropic

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


MODEL = "claude-sonnet-4-6"


def _template_reason(item: dict) -> str:
    t = item["suggestion_type"].replace("_", " ")
    return f"This {t} ({item['size_mb']:.1f} MB) hasn't been accessed in {item['last_accessed_days_ago']} days."


def generate_batch_reasons(items: list[dict], module: str) -> dict[str, str]:
    """
    items: list of dicts with keys: id, filename, size_mb, last_accessed_days_ago, suggestion_type
    Returns: dict mapping item id → one-sentence reason string
    """
    if not items:
        return {}

    client = _get_client()
    if not client.api_key:
        return {item["id"]: _template_reason(item) for item in items}

    lines = "\n".join(
        f'{i+1}. id={item["id"]} | file="{item["filename"]}" | '
        f'size={item["size_mb"]:.1f}MB | age={item["last_accessed_days_ago"]}d | type={item["suggestion_type"]}'
        for i, item in enumerate(items)
    )

    prompt = (
        "You are a file cleanup assistant. For each file below, write exactly one concise sentence "
        "explaining why it should be cleaned up. Mention the file's actual age, size, or type. "
        "Return ONLY lines in the format: <id>=<reason>\n\n" + lines
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=min(80 * len(items), 4096),
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        result: dict[str, str] = {}
        for line in text.strip().splitlines():
            if "=" in line:
                parts = line.split("=", 1)
                item_id = parts[0].strip().lstrip("0123456789. ")
                reason = parts[1].strip()
                if item_id:
                    result[item_id] = reason
        # fill missing with template
        for item in items:
            if item["id"] not in result:
                result[item["id"]] = _template_reason(item)
        return result
    except Exception:
        return {item["id"]: _template_reason(item) for item in items}
