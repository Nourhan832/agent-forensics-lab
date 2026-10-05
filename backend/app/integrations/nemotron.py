import os
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

from dotenv import load_dotenv
from openai import OpenAI
from backend.app.api.deployment import integer_env, reserve_model_request, public_output_limit

load_dotenv()

_api_key = os.getenv("NEBIUS_API_KEY")
_base_url = os.getenv("NEBIUS_BASE_URL")
_model = os.getenv("NEBIUS_MODEL")

client = None
_usage_sink = ContextVar("nebius_usage_sink", default=None)
_completion_metadata = ContextVar("completion_metadata", default=None)


class EmptyModelResponse(ValueError):
    """A successful provider response with no decision content."""


@contextmanager
def capture_completion_metadata():
    metadata = {"finish_reason": None, "provider_response_id": None, "provider_request_id": None}
    token = _completion_metadata.set(metadata)
    try:
        yield metadata
    finally:
        _completion_metadata.reset(token)


@contextmanager
def capture_usage():
    """Opt-in request accounting; no prompts, credentials or provider error bodies."""
    samples = []
    token = _usage_sink.set(samples)
    try:
        yield samples
    finally:
        _usage_sink.reset(token)


def model_configuration() -> dict:
    """Safe metadata: never return credentials or provider error bodies."""
    return {"configured": bool(_api_key and _base_url and _model),
            "model": _model, "provider": "Nebius (configured endpoint)"}


def provider_retries():
    return integer_env("NEBIUS_MAX_RETRIES", 1, minimum=0, maximum=3)


def get_client():
    global client
    if not model_configuration()["configured"]:
        raise RuntimeError("Configure NEBIUS_API_KEY, NEBIUS_BASE_URL and NEBIUS_MODEL.")
    if client is None:
        client = OpenAI(api_key=_api_key, base_url=_base_url,
                        timeout=float(os.getenv("NEBIUS_TIMEOUT_SECONDS", "45")),
                        max_retries=provider_retries())
    return client


def generate_response(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    reserve_model_request()
    output_limit = public_output_limit()
    start = perf_counter()
    response = None
    error_type = None
    try:
        response = get_client().chat.completions.create(
            model=_model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}],
            temperature=temperature,
            **({"max_tokens": output_limit} if output_limit else {}),
        )
    except Exception as error:
        error_type = type(error).__name__
        raise
    finally:
        sink = _usage_sink.get()
        if sink is not None:
            usage = getattr(response, "usage", None)
            sink.append({"latency_ms": round((perf_counter() - start) * 1000, 3),
                         "input_tokens": getattr(usage, "prompt_tokens", None),
                         "output_tokens": getattr(usage, "completion_tokens", None),
                         "total_tokens": getattr(usage, "total_tokens", None),
                         "temperature": temperature, "error_type": error_type})

    metadata = _completion_metadata.get()
    if metadata is not None:
        metadata.update({"finish_reason": getattr(response.choices[0], "finish_reason", None),
                         "provider_response_id": getattr(response, "id", None),
                         "provider_request_id": getattr(response, "_request_id", None)})
    content = response.choices[0].message.content
    if not content:
        raise EmptyModelResponse("Model returned an empty response.")
    return content
