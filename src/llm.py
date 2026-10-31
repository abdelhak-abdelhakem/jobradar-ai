from functools import lru_cache

from langchain_openai import ChatOpenAI

from src.config import LLM_MAX_CONCURRENCY, LLM_MODEL


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Creates the client on first use, so importing a node needs no API key."""
    return ChatOpenAI(model=LLM_MODEL)


def run_batch(chain, inputs: list[dict]) -> list:
    """Runs a chain in parallel. A failed input returns its exception instead of stopping the batch."""
    if not inputs:
        return []
    return chain.batch(
        inputs,
        config={"max_concurrency": LLM_MAX_CONCURRENCY},
        return_exceptions=True,
    )
