"""Thin wrapper around the Google Gen AI SDK on Vertex AI (service-account / ADC auth, no API key)."""
import json
import time

from pipeline.settings import Settings


class GeminiClient:
    def __init__(self, s: Settings):
        from google import genai
        if not s.gcp_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")
        self._types = __import__("google.genai", fromlist=["types"]).types
        self._client = genai.Client(vertexai=True, project=s.gcp_project, location=s.gcp_location)

    def generate_json(self, model: str, parts: list, schema: dict, system: str) -> dict:
        """parts: list of str | (bytes, mime_type). Returns the parsed structured output."""
        from google.genai import errors
        t = self._types
        contents = [p if isinstance(p, str) else t.Part.from_bytes(data=p[0], mime_type=p[1]) for p in parts]
        config = t.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                         response_json_schema=schema, temperature=0.0)
        delay = 10.0
        for attempt in range(7):  # 429 (rate limit) / transient errors: wait and retry
            try:
                resp = self._client.models.generate_content(model=model, contents=contents, config=config)
                return json.loads(resp.text)
            except (errors.ClientError, errors.ServerError) as e:
                if getattr(e, "code", 0) not in (429, 500, 503) or attempt == 6:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 120)
        raise RuntimeError("unreachable")
