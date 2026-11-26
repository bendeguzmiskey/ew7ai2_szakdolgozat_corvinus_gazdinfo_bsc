"""Kapcsolat a nyelvi modellel: Google Gemini API."""
import time
from dataclasses import dataclass

import httpx
from google import genai
from google.genai import errors, types

from . import config

# Időkorlát nélkül egy beragadt hívás megállítaná a futást.
IDOKORLAT_MS = 120_000
_client: genai.Client | None = None


def client() -> genai.Client:
    """A klienst az első hívásnál hozzuk létre, így a tesztekhez nem kell API-kulcs."""
    global _client
    if _client is None:
        if not config.API_KEY:
            raise RuntimeError("Hiányzik a gemini_api_key a kod/.env fájlból.")
        _client = genai.Client(api_key=config.API_KEY, http_options=types.HttpOptions(timeout=IDOKORLAT_MS))
    return _client


@dataclass
class LLMResult:
    text: str
    model_version: str   # a ténylegesen futó modell verziója (méréshez)
    input_tokens: int
    output_tokens: int
    thinking_tokens: int = 0  # a gondolkodó tokeneket is kimenetként számlázzák


def generate(history: list[dict], system_prompt: str, model_key: str = config.DEFAULT_MODEL,
             json_valasz: bool = False, max_tokens: int | None = None) -> LLMResult:
    """A teljes beszélgetést elküldi a modellnek, és visszaadja a választ.

    history: [{"role": "user" | "model", "text": "..."}], időrendben,
             az utolsó elem a hallgató friss üzenete.
    """
    contents = [
        types.Content(role=m["role"], parts=[types.Part(text=m["text"])])
        for m in history
    ]
    cfg = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=config.TEMPERATURE,
        max_output_tokens=max_tokens or config.MAX_OUTPUT_TOKENS,
        response_mime_type="application/json" if json_valasz else None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    # Túlterhelés (503) vagy percenkénti kvóta (429) esetén várunk és újrapróbáljuk.
    for probalkozas in range(5):
        try:
            response = client().models.generate_content(
                model=config.MODELS[model_key], contents=contents, config=cfg)
            break
        except (errors.ServerError, errors.ClientError, httpx.TimeoutException) as e:
            idotullepes = isinstance(e, httpx.TimeoutException)
            if (not idotullepes and getattr(e, "code", None) not in (429, 503)) or probalkozas == 4:
                raise
            time.sleep(5 * 2 ** probalkozas)
    usage = response.usage_metadata
    return LLMResult(
        text=response.text or "",
        model_version=response.model_version or config.MODELS[model_key],
        input_tokens=usage.prompt_token_count or 0,
        output_tokens=usage.candidates_token_count or 0,
        thinking_tokens=getattr(usage, "thoughts_token_count", None) or 0,
    )

