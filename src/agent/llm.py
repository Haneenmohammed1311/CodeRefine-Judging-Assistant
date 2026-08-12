"""
One place that creates the Groq LLM client. Every other file that needs to
"think" imports get_llm() from here, instead of constructing its own client.
This means switching providers later (if you ever do) is a one-file change.
"""

import os
from langchain_groq import ChatGroq

MODEL_NAME = "openai/gpt-oss-120b"

_llm_cache: dict[float, ChatGroq] = {}

def get_llm(temperature: float = 0.0) -> ChatGroq:
    """
    temperature=0.0 by default: for grading, we want consistent, repeatable
    output, not creative variation between runs on the same repo.
    """
    if temperature in _llm_cache:
        return _llm_cache[temperature]
        
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set."
        )
    llm= ChatGroq(model=MODEL_NAME, temperature=temperature, api_key=api_key)
    _llm_cache[temperature] = llm
    return llm 