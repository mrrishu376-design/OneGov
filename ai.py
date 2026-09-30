"""Gemini helpers for OneGov (optional - the app works without a key using keyword routing)."""
import json
import re
import time

FALLBACK_MODEL = "gemini-3.8-flash"
SKIP = ["lite", "image", "tts", "live", "audio", "embed", "native", "robotics"]
_cache = {"models": None}


def client_for(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


def model_list(client):
    if _cache["models"]:
        return _cache["models"]
    found = []
    try:
        for m in client.models.list():
            name = getattr(m, "name", "").replace("models/", "")
            actions = getattr(m, "supported_actions", None) or []
            if "flash" not in name or any(x in name for x in SKIP):
                continue
            if actions and "generateContent" not in actions:
                continue
            ver = tuple(int(n) for n in re.findall(r"\d+", name)[:3]) or (0,)
            found.append((ver, name))
    except Exception:  # noqa: BLE001
        pass
    _cache["models"] = [n for _, n in sorted(found, reverse=True)] or [FALLBACK_MODEL]
    return _cache["models"]


def generate(client, contents):
    """Retry on 503/429 and fall back to the next available Flash model."""
    last = None
    for name in model_list(client)[:3]:
        for _ in range(2):
            try:
                return client.models.generate_content(model=name, contents=contents)
            except Exception as e:  # noqa: BLE001
                last = e
                msg = str(e)
                if "404" in msg or "NOT_FOUND" in msg:
                    break
                if any(x in msg for x in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                    time.sleep(1.5)
                    continue
                raise
    raise last


def parse_json(raw):
    raw = re.sub(r"```json|```", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0) if m else raw)


def route(query, services, api_key):
    """Returns (result or None, error text). result = {service_key, summary}."""
    if not api_key:
        return None, ""
    catalogue = "\n".join(f"- {k}: {v['name']} ({v['dept']}, {v['kind']})" for k, v in services.items())
    prompt = ("A citizen of India typed this request on a government services portal (Hindi, English or Hinglish):\n"
              f"\"{query}\"\n\nChoose the ONE best matching service from this list:\n{catalogue}\n\n"
              'Return ONLY JSON: {"service_key": "<key from the list>", "summary": "<one short English sentence>"}')
    try:
        data = parse_json(generate(client_for(api_key), prompt).text)
        if data.get("service_key") in services:
            return data, ""
        return None, "AI returned an unknown service"
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:160]


def summarize(texts, service_name, api_key):
    if not api_key:
        return None, ""
    prompt = (f"These {len(texts)} citizen complaints are about '{service_name}'. In 2 short sentences (simple English), "
              "state the common problem and the single action the officer should take to fix all of them:\n- " + "\n- ".join(texts))
    try:
        return generate(client_for(api_key), prompt).text.strip(), ""
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:160]
