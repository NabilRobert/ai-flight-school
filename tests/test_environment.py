"""Recording what a run's models really were: a local model is named by its
file's digest and the server's version, so runs whose customers differ
can't be compared, and a model that can't be identified stops the run."""

from typing import Any

import httpx
import pytest
from inspect_ai.model import Model

from flight_school.conversation import environment
from flight_school.conversation.environment import (
    OLLAMA_EXTRA_BODY,
    ModelEnvironmentError,
    max_samples,
    role_model,
    run_models,
)
from flight_school.conversation.records import data_fingerprint
from tests.test_conversation import RULES, WORLD

DIGEST = "7f3251fa6878" + "0" * 52


def ollama_serving(monkeypatch: pytest.MonkeyPatch, models: list[dict[str, Any]]) -> None:
    answers = {"/api/version": {"version": "0.40.11"}, "/api/tags": {"models": models}}

    def get(url: str, timeout: float) -> httpx.Response:
        del timeout
        path = "/api/" + url.rsplit("/api/", 1)[1]
        return httpx.Response(200, json=answers[path], request=httpx.Request("GET", url))

    monkeypatch.setattr(environment.httpx, "get", get)


def test_a_local_customer_is_recorded_with_its_file_and_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama_serving(monkeypatch, [{"name": "qwen3.5:4b", "digest": DIGEST}])
    models = run_models("ollama/qwen3.5:4b", None)
    assert models.customer["model_digest"] == DIGEST
    assert models.customer["ollama_version"] == "0.40.11"
    assert models.agent == {}


def test_the_same_tag_on_a_new_file_makes_runs_incomparable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fingerprints: set[str] = set()
    for digest in (DIGEST, "a" * 64):
        ollama_serving(monkeypatch, [{"name": "qwen3.5:4b", "digest": digest}])
        customer = run_models("ollama/qwen3.5:4b", None).customer
        fingerprints.add(data_fingerprint(WORLD, RULES, customer))
    assert len(fingerprints) == 2


def test_a_local_model_the_server_lacks_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    ollama_serving(monkeypatch, [{"name": "llama3.2:3b", "digest": DIGEST}])
    with pytest.raises(ModelEnvironmentError, match="no model qwen3.5:4b: `ollama list`"):
        run_models(None, "ollama/qwen3.5:4b")


def test_a_server_that_doesnt_answer_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(url: str, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(environment.httpx, "get", refuse)
    with pytest.raises(ModelEnvironmentError, match="is `ollama serve` running"):
        run_models("ollama/qwen3.5:4b", None)


def test_a_hosted_model_is_recorded_by_name_without_asking_ollama() -> None:
    assert run_models("openai/gpt-5-mini", None).customer["model"] == "openai/gpt-5-mini"


def test_a_local_model_runs_with_thinking_off_and_records_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama_serving(monkeypatch, [{"name": "qwen3.5:4b", "digest": DIGEST}])
    model = role_model("ollama/qwen3.5:4b")
    assert isinstance(model, Model)
    assert model.config.extra_body == OLLAMA_EXTRA_BODY
    assert run_models("ollama/qwen3.5:4b", None).customer["extra_body"] == OLLAMA_EXTRA_BODY


def test_a_hosted_model_runs_as_given() -> None:
    assert role_model("openai/gpt-5-mini") == "openai/gpt-5-mini"


def test_chats_on_a_local_model_run_one_at_a_time() -> None:
    # Queued chats would time out for waiting on Ollama, not for being slow.
    assert max_samples(["openai/gpt-5-mini", "ollama/llama3.2:3b"]) == 1


def test_chats_on_hosted_models_keep_inspects_concurrency() -> None:
    assert max_samples(["openai/gpt-5-mini"]) is None
