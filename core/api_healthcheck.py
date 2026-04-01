import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Tuple

import requests

from .utils import env_get, load_env_map


@dataclass
class APICheckResult:
    name: str
    configured: bool
    reachable: bool
    message: str


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _build_config(env: Dict[str, str]) -> Dict[str, str]:
    qdrant_key = env_get("QDRANT_API_KEY", "Quadrant_API_KEY", default="", env_map=env)
    qdrant_url = env_get("QDRANT_URL", "Quadrant_URL", default="", env_map=env)

    if qdrant_key and "|" in qdrant_key and not qdrant_url:
        first, second = qdrant_key.split("|", 1)
        first = first.strip()
        if first.startswith("http://") or first.startswith("https://"):
            qdrant_url = first
        elif "." in first:
            qdrant_url = f"https://{first}"
        else:
            qdrant_url = f"https://{first}.cloud.qdrant.io"
        qdrant_key = second.strip()

    return {
        "groq": env_get("GROQ_API_KEY", "GroqAPIKey", default="", env_map=env),
        "cohere": env_get("COHERE_API_KEY", "CohereAPIKeys", default="", env_map=env),
        "openai": env_get("OPENAI_API_KEY", default="", env_map=env),
        "tavily": env_get("TAVILY_API_KEY", "Tavily_API_KEY", default="", env_map=env),
        "qdrant_key": qdrant_key,
        "qdrant_url": qdrant_url,
        "deepgram": env_get("DEEPGRAM_API_KEY", "Deepgram_API_KEY", default="", env_map=env),
        "playwright": env_get("PLAYWRIGHT_API_KEY", "Playwright_API_KEY", default="", env_map=env),
        "openrouter": env_get("OPENROUTER_API_KEY", "OpenRouter_API_KEY", default="", env_map=env),
        "exa": env_get("EXA_API_KEY", default="", env_map=env),
        "olostep": env_get("OLOSTEP_API_KEY", "Olostep_API_KEY", default="", env_map=env),
    }


def _check_tavily(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("Tavily", False, False, "Missing API key")

    try:
        payload = {
            "query": "hello",
            "max_results": 1,
            "search_depth": "basic",
        }
        response = requests.post(
            "https://api.tavily.com/search",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if response.status_code == 200:
            return APICheckResult("Tavily", True, True, "OK")
        return APICheckResult("Tavily", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("Tavily", True, False, f"Error: {exc}")


def _check_qdrant(url: str, api_key: str) -> APICheckResult:
    configured = bool(url and api_key)
    if not configured:
        return APICheckResult("Qdrant", False, False, "Missing URL and/or API key")

    try:
        endpoint = f"{url.rstrip('/')}/collections"
        response = requests.get(endpoint, headers={"api-key": api_key}, timeout=15)
        if response.status_code == 200:
            return APICheckResult("Qdrant", True, True, "OK")
        return APICheckResult("Qdrant", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("Qdrant", True, False, f"Error: {exc}")


def _check_deepgram(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("Deepgram", False, False, "Missing API key")

    try:
        response = requests.get(
            "https://api.deepgram.com/v1/projects",
            headers={"Authorization": f"Token {api_key}"},
            timeout=15,
        )
        if response.status_code == 200:
            return APICheckResult("Deepgram", True, True, "OK")
        return APICheckResult("Deepgram", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("Deepgram", True, False, f"Error: {exc}")


def _check_groq(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("Groq", False, False, "Missing API key")

    prefix_note = ""
    if not (api_key.startswith("gsk_") or api_key.startswith("gsk-")):
        prefix_note = " (unexpected key format)"

    try:
        response = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if response.status_code == 200:
            return APICheckResult("Groq", True, True, f"OK{prefix_note}")
        return APICheckResult("Groq", True, False, f"HTTP {response.status_code}{prefix_note}")
    except Exception as exc:
        return APICheckResult("Groq", True, False, f"Error: {exc}")


def _check_cohere(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("Cohere", False, False, "Missing API key")

    try:
        response = requests.get(
            "https://api.cohere.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if response.status_code == 200:
            return APICheckResult("Cohere", True, True, "OK")
        return APICheckResult("Cohere", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("Cohere", True, False, f"Error: {exc}")


def _check_openai(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("OpenAI", False, False, "Missing API key")

    try:
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if response.status_code == 200:
            return APICheckResult("OpenAI", True, True, "OK")
        return APICheckResult("OpenAI", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("OpenAI", True, False, f"Error: {exc}")


def _check_openrouter(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("OpenRouter", False, False, "Missing API key")

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if response.status_code == 200:
            return APICheckResult("OpenRouter", True, True, "OK")
        return APICheckResult("OpenRouter", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("OpenRouter", True, False, f"Error: {exc}")


def _check_exa(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("Exa", False, False, "Missing API key")

    try:
        response = requests.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"query": "hello", "numResults": 1},
            timeout=20,
        )
        if response.status_code == 200:
            return APICheckResult("Exa", True, True, "OK")
        return APICheckResult("Exa", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("Exa", True, False, f"Error: {exc}")


def _check_olostep(api_key: str) -> APICheckResult:
    if not api_key:
        return APICheckResult("Olostep", False, False, "Missing API key")

    try:
        response = requests.get(
            "https://api.olostep.com/v1/health",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if response.status_code == 200:
            return APICheckResult("Olostep", True, True, "OK")
        if response.status_code == 404:
            return APICheckResult("Olostep", True, False, "Endpoint not found (key not validated)")
        return APICheckResult("Olostep", True, False, f"HTTP {response.status_code}")
    except Exception as exc:
        return APICheckResult("Olostep", True, False, f"Error: {exc}")


def run_api_healthcheck(env_path: str = ".env") -> Tuple[List[APICheckResult], Dict[str, str]]:
    env = load_env_map(env_path)
    cfg = _build_config(env)

    checks = [
        ("Tavily", lambda: _check_tavily(cfg["tavily"])),
        ("Qdrant", lambda: _check_qdrant(cfg["qdrant_url"], cfg["qdrant_key"])),
        ("Deepgram", lambda: _check_deepgram(cfg["deepgram"])),
        ("Groq", lambda: _check_groq(cfg["groq"])),
        ("Cohere", lambda: _check_cohere(cfg["cohere"])),
        ("OpenAI", lambda: _check_openai(cfg["openai"])),
        ("OpenRouter", lambda: _check_openrouter(cfg["openrouter"])),
        ("Exa", lambda: _check_exa(cfg["exa"])),
        ("Olostep", lambda: _check_olostep(cfg["olostep"])),
    ]
    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        futures = [executor.submit(fn) for _, fn in checks]
        results = [future.result() for future in futures]

    masked = {
        "TAVILY_API_KEY": _mask(cfg["tavily"]),
        "QDRANT_URL": cfg["qdrant_url"],
        "QDRANT_API_KEY": _mask(cfg["qdrant_key"]),
        "DEEPGRAM_API_KEY": _mask(cfg["deepgram"]),
        "GROQ_API_KEY": _mask(cfg["groq"]),
        "COHERE_API_KEY": _mask(cfg["cohere"]),
        "OPENAI_API_KEY": _mask(cfg["openai"]),
        "PLAYWRIGHT_API_KEY": _mask(cfg["playwright"]),
        "OPENROUTER_API_KEY": _mask(cfg["openrouter"]),
        "EXA_API_KEY": _mask(cfg["exa"]),
        "OLOSTEP_API_KEY": _mask(cfg["olostep"]),
    }

    return results, masked


def render_health_report(results: List[APICheckResult], masked_config: Dict[str, str]) -> str:
    lines = ["API Health Check", "", "Configured keys"]
    for key, value in masked_config.items():
        state = value if value else "MISSING"
        lines.append(f"- {key}: {state}")

    lines.append("")
    lines.append("Live checks")
    for item in results:
        if item.configured and item.reachable:
            status = "OK"
        elif item.configured:
            status = "FAILED"
        else:
            status = "MISSING"
        lines.append(f"- {item.name}: {status} ({item.message})")

    failed = {item.name: item for item in results if item.configured and not item.reachable}
    if failed:
        lines.append("")
        lines.append("Quick fix hints")
        if "Groq" in failed:
            lines.append("- Groq: regenerate key from Groq dashboard and use GROQ_API_KEY with gsk_ prefix.")
        if "Qdrant" in failed:
            lines.append("- Qdrant: verify QDRANT_URL host resolves and matches your cluster endpoint exactly.")
            lines.append("- Qdrant: keep QDRANT_API_KEY separate from URL (do not combine in one value).")
        if "Olostep" in failed:
            lines.append("- Olostep: check key scope/plan permissions; HTTP 403 indicates auth is recognized but not authorized.")
        if "OpenAI" in failed:
            lines.append("- OpenAI: ensure key is active in the correct organization/project and billing is enabled.")
        if "OpenRouter" in failed:
            lines.append("- OpenRouter: confirm key is active and account has sufficient credits.")
        if "Exa" in failed:
            lines.append("- Exa: validate API key and ensure your request quota is available.")
        if "Tavily" in failed:
            lines.append("- Tavily: verify key and allowed usage limits in Tavily dashboard.")
        if "Deepgram" in failed:
            lines.append("- Deepgram: check key validity and project permissions.")
        if "Cohere" in failed:
            lines.append("- Cohere: verify key status and model-access permissions.")

    lines.append("")
    lines.append("Notes")
    lines.append("- Playwright does not require an API key for local browser automation.")
    lines.append("- If Qdrant is missing URL, set QDRANT_URL and QDRANT_API_KEY explicitly.")
    return "\n".join(lines)


def main():
    results, masked = run_api_healthcheck()
    print(render_health_report(results, masked))


if __name__ == "__main__":
    main()
