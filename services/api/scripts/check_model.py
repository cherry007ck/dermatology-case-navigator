"""Check that MODEL_API_KEY can access MODEL_NAME at MODEL_BASE_URL. Prints availability only.

    python -m scripts.check_model

Never prints the key, the model list contents or provider error text: only the host contacted,
how many models the key can see, and whether the exact requested model ID is among them.
"""
from __future__ import annotations

import sys
import time
from urllib.parse import urlparse

from app.config import get_settings


def main() -> int:
    s = get_settings()
    if not (s.model_api_key and s.model_base_url and s.model_name):
        print("check_model: FAILED - MODEL_API_KEY, MODEL_BASE_URL and MODEL_NAME must all be set.", file=sys.stderr)
        return 1
    from openai import APIStatusError, OpenAI

    client = OpenAI(api_key=s.model_api_key, base_url=s.model_base_url, timeout=20.0, max_retries=0)
    print(f"check_model: contacting host {urlparse(str(client.base_url)).hostname}")
    start = time.monotonic()
    try:
        ids = [m.id for m in client.models.list()]
    except APIStatusError as exc:
        print(f"check_model: FAILED - HTTP {exc.status_code}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"check_model: FAILED - {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"check_model: key can list {len(ids)} model(s) in {time.monotonic() - start:.2f}s")
    if s.model_name not in ids:
        print(f"check_model: FAILED - requested model {s.model_name!r} is NOT available to this key", file=sys.stderr)
        return 1
    print(f"check_model: PASS - requested model {s.model_name!r} is available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
