"""specs/11-interfaz-web.feature: the local web UI, with a scripted model and fake commands."""

import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from morpho.agent import Agent, ConversationState
from morpho.config import Settings
from morpho.evals.golden import load_golden
from morpho.llm.base import LLMUnavailableError, ToolCall
from morpho.llm.fake import FakeLLM, FakeReply
from morpho.records import HandoffLog, TraceLog
from morpho.retrieval.retriever import Hit, load_thresholds
from morpho.web.server import SCENARIOS, InvalidKeyError, WebState, create_app, main

KEY = "sk-ant-test-key-0123456789"


class _Retriever:
    def retrieve(self, question: str) -> list[Hit]:
        return [Hit("doc1", 0.62)] if "garantía" in question else []


def _agent(replies: list[FakeReply | str]) -> Agent:
    return Agent(
        llm=FakeLLM(replies=replies),
        retriever=_Retriever(),
        handoffs=HandoffLog(None),
        traces=TraceLog(None),
    )


def _check_key(key: str) -> None:
    if key != KEY:
        raise InvalidKeyError("rejected")


def _state(
    *, key: str | None = None, replies: tuple[FakeReply | str, ...] = (), **overrides: Any
) -> WebState:
    env = {"ANTHROPIC_API_KEY": key} if key else {}
    fields: dict[str, Any] = {
        "build_agent": lambda _settings: _agent(list(replies)),
        "check_key": _check_key,
        **overrides,
    }
    return WebState(settings=Settings.from_env(env), **fields)


@pytest.fixture
def client_for() -> Iterator[Any]:
    clients: list[TestClient] = []

    def make(state: WebState) -> TestClient:
        client = TestClient(create_app(state), base_url="http://127.0.0.1:8000")
        client.__enter__()  # runs the startup hook
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


def test_page_and_its_assets_are_served(client_for: Any) -> None:
    client = client_for(_state())
    page = client.get("/")
    assert page.status_code == 200
    assert "Morpho" in page.text
    assert client.get("/static/app.js").status_code == 200


def test_without_a_key_the_page_says_so_and_chat_is_refused(client_for: Any) -> None:
    client = client_for(_state())
    status = client.get("/api/status").json()
    assert status["has_key"] is False
    assert status["model"] == "claude-haiku-4-5"
    assert status["tau"] == load_thresholds(status["embedding_model"]).tau
    assert client.post("/api/chat", json={"message": "hola"}).status_code == 409


def test_key_from_env_is_used_at_startup(client_for: Any) -> None:
    status = client_for(_state(key=KEY)).get("/api/status").json()
    assert (status["has_key"], status["key_source"]) == (True, "env")


@pytest.mark.parametrize(
    ("key", "code"),
    [("hola", 400), ("sk-ant-wrong", 401)],
)
def test_bad_keys_are_rejected(client_for: Any, key: str, code: int) -> None:
    client = client_for(_state())
    response = client.post("/api/key", json={"key": key})
    assert response.status_code == code
    assert client.get("/api/status").json()["has_key"] is False


def test_pasted_key_is_used_but_never_returned(client_for: Any) -> None:
    built: list[Settings] = []

    def build(settings: Settings) -> Agent:
        built.append(settings)
        return _agent([])

    client = client_for(_state(build_agent=build))
    response = client.post("/api/key", json={"key": f"  {KEY} "})
    assert response.status_code == 200
    assert (response.json()["has_key"], response.json()["key_source"]) == (True, "ui")
    assert built[-1].anthropic_api_key == KEY
    assert KEY not in response.text + client.get("/api/status").text


def test_chat_shows_what_happened_in_the_turn(client_for: Any) -> None:
    reply = FakeReply(
        "Tu pedido ORD-1001 está En tránsito, llega en 3 días hábiles.",
        (ToolCall("consultar_estado_pedido", {"order_id": "ORD-1001"}),),
    )
    client = client_for(_state(key=KEY, replies=(reply, "Las lavadoras: 12 meses [Doc1].")))

    first = client.post("/api/chat", json={"message": "¿Cómo va mi pedido ORD-1001?"}).json()
    assert first["path"] == "answered"
    assert first["path_label"] == "Respondió con el modelo"
    assert first["lookups"][0]["estado"] == "En tránsito"
    assert first["validation_problems"] == []
    assert first["llm_requests"] == 2
    assert first["input_tokens"] == 1000

    second = client.post(
        "/api/chat",
        json={"conversation_id": first["conversation_id"], "message": "¿Y la garantía?"},
    ).json()
    assert second["conversation_id"] == first["conversation_id"]
    assert second["retrieved"] == [
        {"doc_id": "doc1", "title": "Política de garantía", "score": 0.62}
    ]
    assert second["citations"] == ["doc1"]


def test_escalation_shows_the_handoff_reference(client_for: Any) -> None:
    client = client_for(_state(key=KEY))
    turn = client.post("/api/chat", json={"message": "Quiero hablar con un asesor"}).json()
    assert turn["path"] == "escalated"
    assert turn["reasons"] == [{"id": "HUMAN_REQUEST", "label": "solicitud de asesor"}]
    assert turn["handoff"]["reference"] in turn["answer"]
    assert turn["llm_requests"] == 0


def test_model_errors_become_a_message(client_for: Any) -> None:
    state = _state(key=KEY)
    client = client_for(state)

    class _Failing:
        def run_turn(self, raw_message: str, state: ConversationState) -> Any:
            raise LLMUnavailableError("APIConnectionError: connection reset")

    state.agent = _Failing()
    response = client.post("/api/chat", json={"message": "¿Cuánto dura la garantía?"})
    assert response.status_code == 502
    assert "connection reset" in response.json()["error"]


def test_scenarios_come_from_the_golden_set(client_for: Any) -> None:
    cases = {case.id: case for case in load_golden()}
    items = client_for(_state()).get("/api/scenarios").json()
    assert len(items) == len(SCENARIOS)  # none silently dropped
    for item in items:
        assert item["text"] == cases[item["id"]].turns[0]


def _fake_pytest(tmp_path: Path) -> dict[str, Any]:
    (tmp_path / "tests").mkdir()
    script = (
        "import os; "
        f"print('con key' if os.environ.get('ANTHROPIC_API_KEY') == {KEY!r} else 'sin key'); "
        "print('11 passed in 0.1s')"
    )
    return {"repo_root": tmp_path, "live_tests": (sys.executable, "-c", script)}


def test_live_tests_stream_their_output_with_the_key(client_for: Any, tmp_path: Path) -> None:
    state = _state(key=KEY, **_fake_pytest(tmp_path))
    client = client_for(state)
    output = client.post("/api/tests/live", json={}).text
    assert "$ uv run pytest -m live" in output
    assert "con key" in output
    assert "11 passed" in output
    assert "[exit 0]" in output
    assert state.tests_running is False


def test_live_tests_need_a_key_and_a_copy_of_the_repo(client_for: Any, tmp_path: Path) -> None:
    no_key = client_for(_state(**_fake_pytest(tmp_path)))
    assert no_key.post("/api/tests/live", json={}).status_code == 409
    no_repo = client_for(_state(key=KEY, repo_root=None))
    assert no_repo.get("/api/status").json()["tests_available"] is False
    assert no_repo.post("/api/tests/live", json={}).status_code == 409


def _wait_for_embedder(client: TestClient) -> dict[str, Any]:
    for _ in range(100):
        status = client.get("/api/status").json()
        if status["embedder"] != "loading":
            return status
        time.sleep(0.01)
    raise AssertionError("the warm-up never finished")


def test_embedding_model_warms_up_in_the_background(client_for: Any) -> None:
    status = _wait_for_embedder(client_for(_state(warm_up=lambda: None)))
    assert status["embedder"] == "ready"


def test_a_failed_warm_up_is_reported(client_for: Any) -> None:
    def fail() -> None:
        raise OSError("no network")

    status = _wait_for_embedder(client_for(_state(warm_up=fail)))
    assert status["embedder"] == "error"
    assert "no network" in status["embedder_error"]


def test_page_explains_how_to_add_the_key(client_for: Any) -> None:
    page = client_for(_state()).get("/").text
    assert ".env" in page
    assert "ANTHROPIC_API_KEY" in page


def test_pasted_key_is_never_written_to_disk(
    client_for: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    client = client_for(_state())
    assert client.post("/api/key", json={"key": KEY}).status_code == 200
    client.post("/api/chat", json={"message": "Quiero hablar con un asesor"})
    assert not any(KEY in path.read_text() for path in tmp_path.rglob("*") if path.is_file())


# --- requests from other sites (any page open in the browser could otherwise spend the key)


def test_form_posts_from_other_sites_are_refused(client_for: Any) -> None:
    client = client_for(_state(key=KEY))
    body = '{"message": "hola"}'
    response = client.post("/api/chat", content=body, headers={"Content-Type": "text/plain"})
    assert response.status_code == 415
    assert client.post("/api/tests/live").status_code == 415


def test_requests_from_another_origin_are_refused(client_for: Any) -> None:
    client = client_for(_state(key=KEY))
    headers = {"Origin": "https://evil.example"}
    response = client.post("/api/chat", json={"message": "hola"}, headers=headers)
    assert response.status_code == 403
    same = client.post(
        "/api/chat", json={"message": "hola"}, headers={"Origin": "http://127.0.0.1:8000"}
    )
    assert same.status_code == 200


def test_unknown_host_names_are_refused(client_for: Any) -> None:
    client = client_for(_state(key=KEY))
    assert client.get("/api/status", headers={"Host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("body", ["{oops", "[1, 2]"])
def test_malformed_bodies_get_a_clear_error(client_for: Any, body: str) -> None:
    client = client_for(_state(key=KEY))
    headers = {"Content-Type": "application/json"}
    assert client.post("/api/chat", content=body, headers=headers).status_code == 400


# --- the single command


def test_one_command_serves_on_localhost_and_opens_the_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    import uvicorn

    served: dict[str, Any] = {}
    opened: list[str] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: served.update(kwargs))

    class _Timer:
        def __init__(self, _delay: float, function: Any, args: list[str]) -> None:
            self.function, self.args = function, args

        def start(self) -> None:
            opened.extend(self.args)

    monkeypatch.setattr(threading, "Timer", _Timer)
    assert main(["--port", "8765"]) == 0
    assert served["host"] == "127.0.0.1"
    assert opened == [f"http://127.0.0.1:{served['port']}"]
