"""What a model in a run really was, for the records' provenance.

A model customer is part of the test's environment: a different model
file or server build gives different customers, so two runs with
different ones must not be compared (thesis pilot). For a local model on
Ollama, the name alone isn't enough (a tag can be pulled again and point
at a new file), so the file's digest and Ollama's version are recorded
too, with the settings it runs with. Other models are recorded by name.
They are read before the run starts, so a missing model fails in seconds,
not after hours.
"""

import os
from dataclasses import dataclass

import httpx

from inspect_ai.model import GenerateConfig, Model, get_model

OLLAMA_PREFIX = "ollama/"
# Inspect's own default for its Ollama provider, which also reads this
# variable (inspect_ai/model/_providers/ollama.py).
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_TIMEOUT_SECONDS = 10
# Small local models may think before every line by default (qwen3.5 does).
# In the smoke check, one customer line took 118 s and 2,265 tokens with
# thinking and about 3 s without; the chat only uses the line, so an
# Ollama model runs with thinking off. Sent as Ollama's own field, since
# Inspect drops a reasoning effort of "none" for Ollama.
OLLAMA_EXTRA_BODY = {"reasoning": {"effort": "none"}}
# How a model customer is seeded (customer.py: customer_seed), recorded so
# a reader knows two runs drew the same customers.
CUSTOMER_SEED_RULE = "sha256(task_id#epoch), first 4 bytes"
# Chats run one at a time when a role is a local model. Inspect would run
# 10 at once, but Ollama answers one or a few requests at a time, so the
# rest queue, and the per-chat time limit (plan.py) counts the queueing:
# chats would time out for waiting, not for being slow.
LOCAL_MAX_SAMPLES = 1

Environment = dict[str, object]


class ModelEnvironmentError(Exception):
    """A model's file or server couldn't be identified for the records."""


def model_environment(model: str | Model) -> Environment:
    name = str(model)
    if not name.startswith(OLLAMA_PREFIX):
        return {"model": name}
    details = ollama_details(name.removeprefix(OLLAMA_PREFIX))
    return {"model": name, **details, "extra_body": OLLAMA_EXTRA_BODY}


def role_model(model: str | Model) -> str | Model:
    """The model to run in a role: an Ollama model by name gets the
    settings above; anything else runs as given."""
    if isinstance(model, Model) or not model.startswith(OLLAMA_PREFIX):
        return model
    return get_model(model, config=GenerateConfig(extra_body=OLLAMA_EXTRA_BODY))


def max_samples(models: list[str | Model]) -> int | None:
    """How many chats may run at once; None leaves Inspect's default."""
    if any(str(model).startswith(OLLAMA_PREFIX) for model in models):
        return LOCAL_MAX_SAMPLES
    return None


def ollama_details(tag: str) -> Environment:
    base = os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL).removesuffix("/v1")
    try:
        version = httpx.get(f"{base}/api/version", timeout=OLLAMA_TIMEOUT_SECONDS).json()
        models = httpx.get(f"{base}/api/tags", timeout=OLLAMA_TIMEOUT_SECONDS).json()["models"]
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise ModelEnvironmentError(
            f"can't read the model's details from Ollama at {base} ({error}): is `ollama serve`"
            " running? The records need them to tell two customer models apart."
        ) from error
    digest = next((entry["digest"] for entry in models if entry["name"] == tag), None)
    if digest is None:
        raise ModelEnvironmentError(
            f"Ollama at {base} has no model {tag}: `ollama list` shows what it has."
        )
    return {"model_digest": digest, "ollama_version": version["version"]}


@dataclass(frozen=True)
class RunModels:
    # The customer side, as it goes in the data fingerprint.
    customer: Environment
    # A model-backed agent's model; empty for an agent that calls none here.
    agent: Environment


def run_models(customer_model: str | Model | None, agent_model: str | Model | None) -> RunModels:
    customer: Environment = {"model": "scripted"}
    if customer_model is not None:
        customer = {**model_environment(customer_model), "seed": CUSTOMER_SEED_RULE}
    agent = {} if agent_model is None else model_environment(agent_model)
    return RunModels(customer, agent)
