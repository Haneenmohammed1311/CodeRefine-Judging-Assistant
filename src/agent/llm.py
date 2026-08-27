"""
One place that creates the LLM clients. Every other file that needs to
"think" imports get_llm() from here, instead of constructing its own client.

1. Primary: openai/gpt-oss-120b (High capability, fast)
2. Fallback: llama-3.3-70b-versatile (Free backup if primary rate limits)
"""

import os
from langchain_groq import ChatGroq

MODEL_NAME = "openai/gpt-oss-120b"
FALLBACK_MODEL_NAME = "llama/llama-3.3-70b-versatile"
VISION_MODEL_NAME = "qwen/qwen3.6-27b"


_llm_cache: dict[tuple[float, bool], ChatGroq] = {}
_vision_llm_cache: dict[tuple[float, bool], ChatGroq] = {}


def get_llm(temperature: float = 0.0, json_mode: bool = False) -> ChatGroq:
    """
    temperature=0.0 by default: for grading, we want consistent, repeatable
    output, not creative variation between runs on the same repo.
    """
    cache_key = (temperature, json_mode)
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set."
        )
    # 1. Primary Model (Groq 120B)
    primary_llm = ChatGroq(model=MODEL_NAME,temperature=temperature,api_key=api_key,)

    # 2. Backup Model (Groq Llama-3.3-70B)
    fallback_llm = ChatGroq( model=FALLBACK_MODEL_NAME,temperature=temperature,api_key=api_key,)    
    if json_mode:
        primary_llm = primary_llm.bind(response_format={"type": "json_object"})
        fallback_llm = fallback_llm.bind(response_format={"type": "json_object"})

    # Chain primary with fallback
    robust_llm = primary_llm.with_fallbacks([fallback_llm])
    
    _llm_cache[cache_key] = robust_llm
    return robust_llm


def get_vision_llm(temperature: float = 0.0, json_mode: bool = False) -> ChatGroq:
    """Returns the separate Groq vision client used only for repository diagrams."""
    cache_key = (temperature, json_mode)
    if cache_key in _vision_llm_cache:
        return _vision_llm_cache[cache_key]

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set.")

    llm = ChatGroq(model=VISION_MODEL_NAME, temperature=temperature, api_key=api_key)
    if json_mode:
        llm = llm.bind(response_format={"type": "json_object"})
    _vision_llm_cache[cache_key] = llm
    return llm
