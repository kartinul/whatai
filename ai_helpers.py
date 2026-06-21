import os
import re
import time
import threading
from collections import deque
from google import genai

MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
RPM = 15


class ModelClient:
    """One specific (model, api_key) pair with its own rate limit tracking."""

    def __init__(self, model: str, api_key: str) -> None:
        self.model = model
        self.api_key = api_key
        self._client = genai.Client(api_key=api_key)
        self._history: deque[float] = deque()
        self._lock = threading.Lock()
        self._cooldown_until: float = 0.0

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """True if this client is not on cooldown and under the RPM limit."""
        if time.time() < self._cooldown_until:
            return False
        with self._lock:
            now = time.time()
            while self._history and now - self._history[0] >= 60:
                self._history.popleft()
            return len(self._history) < RPM

    def _stamp(self) -> None:
        with self._lock:
            self._history.append(time.time())

    def cooldown(self, seconds: float = 60.0) -> None:
        self._cooldown_until = time.time() + seconds

    # ------------------------------------------------------------------
    # Call
    # ------------------------------------------------------------------

    def call(self, system: str, prompt: str) -> str:
        self._stamp()
        print(f"[llm] {self.model} | key ...{self.api_key[-4:]}")
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(system_instruction=system),
        )
        return resp.text

    def __repr__(self) -> str:
        return f"ModelClient(model={self.model!r}, key=...{self.api_key[-4:]})"


# ------------------------------------------------------------------
# Pool -- one ModelClient per (model x key) combination
# ------------------------------------------------------------------

_pool: list[ModelClient] | None = None
_pool_lock = threading.Lock()


def _get_pool() -> list[ModelClient]:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                keys = [
                    os.environ[k].strip()
                    for k in sorted(os.environ)
                    if k.startswith("GEMINI_KEY_") and os.environ[k].strip()
                ]
                if not keys:
                    raise ValueError("No GEMINI_KEY_* found in environment.")
                # Models-first order: exhaust all keys for the best model
                # before falling back to the next model.
                _pool = [
                    ModelClient(model, key)
                    for model in MODELS
                    for key in keys
                ]
    return _pool


def _parse_retry_after(exc: Exception) -> float:
    """
    Extract retry-after seconds from a Gemini 429 exception.

    The SDK embeds a RetryInfo proto in the error body, e.g.:
      {'details': [{'@type': '.../RetryInfo', 'retryDelay': '3600s'}]}

    We try JSON first, then fall back to regex on the raw string.
    """
    import json

    raw = str(exc)

    # --- Try structured JSON in exception args ---
    for arg in getattr(exc, 'args', []):
        text = arg if isinstance(arg, str) else str(arg)
        # find the first {...} block
        start = text.find('{')
        if start == -1:
            continue
        try:
            body = json.loads(text[start:])
            for detail in body.get('details', []) or body.get('error', {}).get('details', []):
                delay_str = detail.get('retryDelay', '')
                m = re.match(r'(\d+)', delay_str)
                if m:
                    return float(m.group(1))
        except (json.JSONDecodeError, AttributeError):
            pass

    # --- Regex fallback on the raw string ---
    # gRPC proto:  retry_delay { seconds: 3600 }
    m = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', raw, re.IGNORECASE)
    if m:
        return float(m.group(1))

    # plain seconds / minutes / hours
    m = re.search(r'retry\s+after\s+(\d+)\s*s', raw, re.IGNORECASE)
    if m:
        return float(m.group(1))

    m = re.search(r'wait\s+(\d+)\s*(minute|min|hour|hr)', raw, re.IGNORECASE)
    if m:
        n, unit = float(m.group(1)), m.group(2).lower()
        return n * 3600 if unit.startswith('h') else n * 60

    return 60.0  # safe default


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def call_llm(system: str, prompt: str) -> str:
    """
    Try each (model, key) client in priority order.
    Blocks until a slot opens or the overall timeout is hit.
    """
    pool = _get_pool()
    deadline = time.time() + 120  # overall timeout

    while time.time() < deadline:
        for client in pool:
            if not client.is_available():
                continue
            try:
                return client.call(system, prompt)
            except Exception as e:
                msg = str(e)
                print(f"[llm] {client} failed: {msg}")

                if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                    wait = _parse_retry_after(e)
                    print(f"[llm] rate-limited -- cooling {client} for {wait:.0f}s "
                          f"({wait / 60:.1f} min)")
                    client.cooldown(wait)

                elif "503" in msg or "UNAVAILABLE" in msg:
                    client.cooldown(60)

                else:
                    time.sleep(1)

        time.sleep(0.5)

    raise RuntimeError("All ModelClients exhausted or on cooldown.")
