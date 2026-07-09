"""
Multi-provider XAI fallback chain.

Providers are tried in order (cheapest / most generous free tier first).
Any exception (quota exhausted, missing key, network error) causes an
automatic fallback to the next provider.  If every provider fails, a
deterministic template string is returned — the app always gets a reason.

Required env vars (set the ones you have; unset ones are silently skipped):
  GROQ_API_KEY       — Groq (llama-3.3-70b-versatile,  free tier)
  GOOGLE_API_KEY     — Gemini 2.0 Flash + Gemini 1.5 Flash
  MISTRAL_API_KEY    — Mistral Small
  DEEPSEEK_API_KEY   — DeepSeek Chat (OpenAI-compatible)
  COHERE_API_KEY     — Cohere Command-R+
  ANTHROPIC_API_KEY  — Claude Haiku + Claude Sonnet
  OPENAI_API_KEY     — GPT-4o Mini + GPT-4o
"""

import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _template_reason(item: dict) -> str:
    t = item["suggestion_type"].replace("_", " ")
    return (
        f"This {t} ({item['size_mb']:.1f} MB) hasn't been accessed "
        f"in {item['last_accessed_days_ago']} days."
    )


def _build_prompt(items: list[dict]) -> str:
    lines = "\n".join(
        f'{i + 1}. id={item["id"]} | file="{item["filename"]}" | '
        f'size={item["size_mb"]:.1f}MB | age={item["last_accessed_days_ago"]}d | type={item["suggestion_type"]}'
        for i, item in enumerate(items)
    )
    return (
        "You are a file cleanup assistant. For each file below, write exactly one concise sentence "
        "explaining why it should be cleaned up. Mention the file's actual age, size, or type. "
        "Return ONLY lines in the format: <id>=<reason>\n\n" + lines
    )


def _parse_reasons(text: str, items: list[dict]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.strip().splitlines():
        if "=" in line:
            parts = line.split("=", 1)
            item_id = parts[0].strip().lstrip("0123456789. ")
            reason = parts[1].strip()
            if item_id:
                result[item_id] = reason
    # fill any missed items with the template
    for item in items:
        if item["id"] not in result:
            result[item["id"]] = _template_reason(item)
    return result


# ---------------------------------------------------------------------------
# Provider functions — each returns the raw text or raises any exception
# ---------------------------------------------------------------------------

def _try_groq(prompt: str, max_tokens: int) -> str:
    """Groq — llama-3.3-70b-versatile (free tier, very fast)"""
    import groq  # type: ignore
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise ValueError("No GROQ_API_KEY")
    client = groq.Groq(api_key=key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _try_gemini_flash_20(prompt: str, max_tokens: int) -> str:
    """Google Gemini 2.0 Flash (google-genai SDK)"""
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        raise ValueError("No GOOGLE_API_KEY")
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    return resp.text


def _try_gemini_flash_15(prompt: str, max_tokens: int) -> str:
    """Google Gemini 1.5 Flash (google-genai SDK)"""
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        raise ValueError("No GOOGLE_API_KEY")
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    return resp.text


def _try_mistral(prompt: str, max_tokens: int) -> str:
    """Mistral Small — cheap, European-hosted"""
    from mistralai.client import Mistral  # type: ignore
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        raise ValueError("No MISTRAL_API_KEY")
    client = Mistral(api_key=key)
    resp = client.chat.complete(
        model="mistral-small-latest",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _try_deepseek(prompt: str, max_tokens: int) -> str:
    """DeepSeek Chat — OpenAI-compatible endpoint, very low cost"""
    import openai  # type: ignore
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise ValueError("No DEEPSEEK_API_KEY")
    client = openai.OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _try_cohere(prompt: str, max_tokens: int) -> str:
    """Cohere Command-R+"""
    import cohere  # type: ignore
    key = os.environ.get("COHERE_API_KEY", "")
    if not key:
        raise ValueError("No COHERE_API_KEY")
    client = cohere.ClientV2(api_key=key)
    resp = client.chat(
        model="command-r-plus-08-2024",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.message.content[0].text


def _try_claude_haiku(prompt: str, max_tokens: int) -> str:
    """Anthropic Claude Haiku — fast, low cost"""
    from anthropic import Anthropic  # type: ignore
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("No ANTHROPIC_API_KEY")
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _try_gpt4o_mini(prompt: str, max_tokens: int) -> str:
    """OpenAI GPT-4o Mini"""
    import openai  # type: ignore
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("No OPENAI_API_KEY")
    client = openai.OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def _try_claude_sonnet(prompt: str, max_tokens: int) -> str:
    """Anthropic Claude Sonnet — high quality"""
    from anthropic import Anthropic  # type: ignore
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("No ANTHROPIC_API_KEY")
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _try_gpt4o(prompt: str, max_tokens: int) -> str:
    """OpenAI GPT-4o — most capable fallback"""
    import openai  # type: ignore
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("No OPENAI_API_KEY")
    client = openai.OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Ordered fallback chain (index 0 = tried first)
# ---------------------------------------------------------------------------
_PROVIDERS: list[tuple[str, object]] = [
    ("Groq llama-3.3-70b-versatile",  _try_groq),
    ("Gemini 2.0 Flash",              _try_gemini_flash_20),
    ("Gemini 1.5 Flash",              _try_gemini_flash_15),
    ("Mistral Small",                 _try_mistral),
    ("DeepSeek Chat",                 _try_deepseek),
    ("Cohere Command-R+",             _try_cohere),
    ("Claude Haiku",                  _try_claude_haiku),
    ("GPT-4o Mini",                   _try_gpt4o_mini),
    ("Claude Sonnet",                 _try_claude_sonnet),
    ("GPT-4o",                        _try_gpt4o),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_batch_reasons(items: list[dict], module: str) -> dict[str, str]:
    """
    items: list of dicts with keys:
        id, filename, size_mb, last_accessed_days_ago, suggestion_type
    Returns: dict mapping item id → one-sentence reason string

    Tries each provider in _PROVIDERS order.  Any exception (missing key,
    quota, network) causes a silent fallback to the next provider.
    If all fail, returns deterministic template strings — never raises.
    """
    if not items:
        return {}

    max_tokens = min(80 * len(items), 4096)
    prompt = _build_prompt(items)

    for name, provider_fn in _PROVIDERS:
        try:
            text = provider_fn(prompt, max_tokens)  # type: ignore[operator]
            return _parse_reasons(text, items)
        except Exception:
            continue  # try next provider

    # Every provider exhausted — return template strings
    return {item["id"]: _template_reason(item) for item in items}

def get_drive_reason(filename: str, size_mb: float, category: str, days_old: int, mime_type: str) -> str:
    """
    Generates a 1-sentence reason for a Drive file suggestion.
    Uses the same provider fallback chain as generate_batch_reasons.
    Never receives file contents — only metadata.
    """
    prompt = (
        f"In one sentence (max 15 words), explain why this Google Drive file is digital clutter. "
        f"File: '{filename}', type: {mime_type}, size: {size_mb}MB, "
        f"category: {category}, last modified {days_old} days ago. "
        f"Be specific. Do not start with 'This file'."
    )

    templates = {
        "duplicate": f"Exact copy of another file — safe to remove, saving {size_mb:.1f} MB.",
        "large":     f"Large file ({size_mb:.0f} MB) untouched for {days_old} days — consider compressing.",
        "old":       f"Unused for {days_old} days — likely safe to archive or remove.",
        "screenshot": f"Screenshot sitting untouched for {days_old} days.",
        "unused":    f"Never opened in {days_old} days — a strong candidate for cleanup.",
    }

    for name, provider_fn in _PROVIDERS:
        try:
            return provider_fn(prompt, 60)
        except Exception:
            continue

    return templates.get(category, f"Unused {category} file — worth reviewing.")