"""Local web UI: chat with Morpho, see what happened in each turn and run the live tests.

    uv run morpho-ui

Listens on 127.0.0.1 only. The Claude key comes from `.env`, or the reviewer pastes it in the
page: a pasted key lives only in this process's memory. It is never written to disk and never
returned by the API.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import importlib.util
import os
import socket
import sys
import threading
import time
import uuid
import webbrowser
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

import anthropic
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from morpho.agent import ConversationState, TurnResult
from morpho.config import Settings, load_settings
from morpho.evals.golden import load_golden
from morpho.guardrails.output_validator import (
    APPROVAL,
    CITATION,
    DATE,
    DURATION,
    ORDER_ID,
    ORDER_STATUS,
)
from morpho.knowledge.documents import get_document
from morpho.llm.base import LLMUnavailableError
from morpho.records import cost_usd
from morpho.retrieval.embedder import EmbedderUnavailableError
from morpho.retrieval.retriever import NotCalibratedError, load_thresholds

STATIC_DIR = Path(__file__).with_name("static")
DEFAULT_PORT = 8000
LIVE_TESTS = ("-m", "pytest", "-m", "live", "-q", "--color=no", "-p", "no:cacheprovider")
LIVE_TESTS_COMMAND = "uv run pytest -m live"

PATH_LABELS = {
    "answered": "Respondió con el modelo",
    "escalated": "Derivó a un asesor humano",
    "asked_refund_amount": "Pidió el monto en USD",
    "asked_order_id": "Pidió el ID del pedido",
    "replaced": "El validador reemplazó el borrador",
    "abstained": "Sin información: ofreció un asesor",
    "refused": "Rechazó el intento de cambiar sus reglas",
    "empty": "Mensaje vacío",
}
PROBLEM_LABELS = {
    APPROVAL: "aprobaba un reembolso",
    CITATION: "citaba un documento no recuperado",
    ORDER_ID: "mencionaba un pedido no consultado",
    ORDER_STATUS: "daba un estado no consultado",
    DURATION: "daba un plazo que no está en las fuentes",
    DATE: "daba una fecha",
    "empty_answer": "llegó vacío",
    "stop_refusal": "el modelo se negó a responder",
    "stop_max_tokens": "se cortó por longitud",
    "tool_limit": "quedó a mitad de las consultas de pedidos",
}
# Quick prompts for the chat, taken from the golden set so they stay in sync with the eval.
SCENARIOS = (
    ("Garantía", "garantia-lavadora"),
    ("Sin clasificar", "garantia-microondas"),
    ("Envíos", "envio-internacional"),
    ("Pedido", "pedido-con-espacio"),
    ("Cancelado", "pedido-cancelado"),
    ("No existe", "pedido-inexistente"),
    ("Sin ID", "pedido-sin-id"),
    ("Reembolso $500", "reembolso-500"),
    ("Reembolso > $500", "reembolso-500-01"),
    ("Mixto", "pedido-y-cobro-doble"),
    ("Queja", "queja-repartidor"),
    ("Inyección", "inyeccion-aprobar"),
    ("Prompt", "inyeccion-prompt"),
    ("Fuera de tema", "fuera-receta"),
    ("Inglés", "garantia-lavadora-en"),
)


class TurnRunner(Protocol):
    def run_turn(self, raw_message: str, state: ConversationState) -> TurnResult: ...


class InvalidKeyError(ValueError):
    pass


@dataclass
class WebState:
    """What the routes share. Everything slow or external is injected, so tests stay offline."""

    settings: Settings
    build_agent: Callable[[Settings], TurnRunner]
    check_key: Callable[[str], None]
    """Raises `InvalidKeyError` when Anthropic rejects the key."""
    warm_up: Callable[[], None] | None = None
    """Loads the local embedding model in the background, downloading it the first time."""
    repo_root: Path | None = None
    """Where `tests/` lives; the live tests can only run from a clone of the repo."""
    live_tests: Sequence[str] = (sys.executable, *LIVE_TESTS)
    agent: TurnRunner | None = None
    key_source: Literal["env", "ui"] | None = None
    embedder: Literal["loading", "ready", "error"] = "ready"
    embedder_error: str | None = None
    conversations: dict[str, ConversationState] = field(default_factory=dict)
    turn_lock: threading.Lock = field(default_factory=threading.Lock)
    tests_running: bool = False

    def start(self) -> None:
        if self.settings.has_api_key and self.agent is None:
            self.agent = self.build_agent(self.settings)
            self.key_source = "env"
        if self.warm_up is not None:
            self.embedder = "loading"
            threading.Thread(target=self._warm_up, daemon=True).start()

    def _warm_up(self) -> None:
        assert self.warm_up is not None
        try:
            self.warm_up()
            self.embedder = "ready"
        except Exception as exc:  # shown in the page; questions already cached still work
            self.embedder, self.embedder_error = "error", f"{exc.__class__.__name__}: {exc}"

    @property
    def tests_available(self) -> bool:
        return (
            self.repo_root is not None
            and (self.repo_root / "tests").is_dir()
            and importlib.util.find_spec("pytest") is not None
        )


def create_app(
    state: WebState, allowed_hosts: Sequence[str] = ("127.0.0.1", "localhost")
) -> Starlette:
    def index(_: Request) -> Response:
        return FileResponse(STATIC_DIR / "index.html")

    def status(_: Request) -> JSONResponse:
        return JSONResponse(_status(state))

    async def set_key(request: Request) -> JSONResponse:
        body = await _body(request)
        if isinstance(body, JSONResponse):
            return body
        key = str(body.get("key", "")).strip()
        if not key.startswith("sk-ant-"):
            return _error(400, "Eso no parece una API key de Anthropic (empieza con sk-ant-).")
        try:
            await asyncio.to_thread(state.check_key, key)
        except InvalidKeyError:
            return _error(401, "Anthropic rechazó la key. Revisa que esté completa y activa.")
        except anthropic.AnthropicError as exc:
            return _error(502, f"No se pudo verificar la key ({exc.__class__.__name__}).")
        settings = dataclasses.replace(state.settings, anthropic_api_key=key)
        state.agent = await asyncio.to_thread(state.build_agent, settings)
        state.settings, state.key_source = settings, "ui"
        state.conversations.clear()
        return JSONResponse(_status(state))

    async def chat(request: Request) -> JSONResponse:
        body = await _body(request)
        if isinstance(body, JSONResponse):
            return body
        if state.agent is None:
            return _error(409, "Falta la API key de Anthropic.")
        conversation_id = body.get("conversation_id") or uuid.uuid4().hex[:12]
        conversation = state.conversations.setdefault(
            conversation_id, ConversationState(conversation_id=conversation_id)
        )
        try:
            result, latency_ms = await asyncio.to_thread(
                _run_turn, state, str(body.get("message", "")), conversation
            )
        except LLMUnavailableError as exc:
            return _error(502, f"No se pudo contactar al modelo: {exc}")
        except EmbedderUnavailableError as exc:
            return _error(503, f"No se pudo cargar el modelo de embeddings: {exc}")
        return JSONResponse(_turn_payload(state.settings, conversation_id, result, latency_ms))

    def scenarios(_: Request) -> JSONResponse:
        cases = {case.id: case for case in load_golden()}
        items = [
            {"label": label, "id": case_id, "text": cases[case_id].turns[0]}
            for label, case_id in SCENARIOS
            if case_id in cases
        ]
        return JSONResponse(items)

    async def live_tests(request: Request) -> Response:
        rejected = _cross_site(request)
        if rejected is not None:
            return rejected
        if not state.tests_available:
            return _error(409, "Las pruebas solo corren desde una copia del repositorio.")
        if state.agent is None:
            return _error(409, "Falta la API key de Anthropic.")
        if state.tests_running:
            return _error(409, "Las pruebas ya están corriendo.")
        return StreamingResponse(_stream_live_tests(state), media_type="text/plain")

    routes = [
        Route("/", index),
        Route("/api/status", status),
        Route("/api/key", set_key, methods=["POST"]),
        Route("/api/chat", chat, methods=["POST"]),
        Route("/api/scenarios", scenarios),
        Route("/api/tests/live", live_tests, methods=["POST"]),
        Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
    ]

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncGenerator[None]:
        state.start()
        yield

    # Host check: a page that rebinds its own domain to 127.0.0.1 is still refused.
    middleware = [Middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))]
    return Starlette(routes=routes, middleware=middleware, lifespan=lifespan)


def _run_turn(
    state: WebState, message: str, conversation: ConversationState
) -> tuple[TurnResult, float]:
    assert state.agent is not None
    with state.turn_lock:  # one turn at a time: the logs and the history are shared
        started = time.perf_counter()
        result = state.agent.run_turn(message, conversation)
        return result, (time.perf_counter() - started) * 1000


async def _stream_live_tests(state: WebState) -> AsyncIterator[str]:
    env = {**os.environ, "ANTHROPIC_API_KEY": state.settings.anthropic_api_key or ""}
    state.tests_running = True
    process = None
    try:
        yield f"$ {LIVE_TESTS_COMMAND}\n"
        process = await asyncio.create_subprocess_exec(
            *state.live_tests,
            cwd=state.repo_root,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert process.stdout is not None
        async for line in process.stdout:
            yield line.decode(errors="replace")
        code = await process.wait()
        yield f"\n[exit {code}]\n"
    finally:  # also when the page closes mid-run: stop pytest instead of orphaning it
        if process is not None and process.returncode is None:
            process.kill()
        state.tests_running = False


def _status(state: WebState) -> dict[str, Any]:
    settings = state.settings
    try:
        tau: float | None = load_thresholds(settings.embedding_model).tau
    except NotCalibratedError:
        tau = None
    return {
        "has_key": state.agent is not None,
        "key_source": state.key_source,
        "model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "tau": tau,
        "embedder": state.embedder,
        "embedder_error": state.embedder_error,
        "tests_available": state.tests_available,
        "tests_running": state.tests_running,
        "live_tests_command": LIVE_TESTS_COMMAND,
    }


def _turn_payload(
    settings: Settings, conversation_id: str, result: TurnResult, latency_ms: float
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "answer": result.answer,
        "path": result.path,
        "path_label": PATH_LABELS.get(result.path, result.path),
        "language": result.language,
        "reasons": [{"id": r.value, "label": r.label} for r in result.reasons],
        "handoff": (
            {"reference": result.handoff.reference, "summary": result.handoff.summary}
            if result.handoff
            else None
        ),
        "retrieved": [
            {"doc_id": hit.doc_id, "title": get_document(hit.doc_id).title, "score": hit.score}
            for hit in result.retrieved
        ],
        "citations": list(result.citations),
        "lookups": list(result.lookups),
        "validation_problems": [PROBLEM_LABELS.get(p, p) for p in result.validation_problems],
        "llm_requests": result.llm_requests,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cost_usd": cost_usd(settings.llm_model, result.usage),
        "latency_ms": round(latency_ms),
    }


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _cross_site(request: Request) -> JSONResponse | None:
    """Refuses requests another site could send from the reviewer's browser.

    Requiring a JSON body makes the browser ask permission first (a CORS preflight this server
    never grants), and an Origin from another site is refused outright. Without this, any page
    open while the UI runs could spend the Claude key through /api/chat.
    """
    if not request.headers.get("content-type", "").startswith("application/json"):
        return _error(415, "La petición debe ser JSON.")
    origin = request.headers.get("origin")
    if origin is not None and urlsplit(origin).netloc != request.headers.get("host"):
        return _error(403, "Origen no permitido.")
    return None


async def _body(request: Request) -> dict[str, Any] | JSONResponse:
    rejected = _cross_site(request)
    if rejected is not None:
        return rejected
    try:
        body = await request.json()
    except ValueError:
        return _error(400, "El cuerpo de la petición no es JSON válido.")
    if not isinstance(body, dict):
        return _error(400, "El cuerpo de la petición debe ser un objeto JSON.")
    return body


def _check_key(key: str) -> None:
    import anthropic

    try:
        anthropic.Anthropic(api_key=key).models.list(limit=1)
    except anthropic.AuthenticationError as exc:
        raise InvalidKeyError(str(exc)) from exc


def _free_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise OSError(f"no free port between {start} and {start + 19}")


def _repo_root() -> Path | None:
    root = Path(__file__).resolve().parents[3]  # src/morpho/web/server.py -> repo root
    return root if (root / "pyproject.toml").is_file() else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interfaz web local de Morpho.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="no abrir el navegador")
    args = parser.parse_args(argv)

    import uvicorn

    from morpho.app import build_agent
    from morpho.retrieval.embedder import FastEmbedEmbedder

    settings = load_settings()
    local = FastEmbedEmbedder(settings.embedding_model, settings.models_dir)
    state = WebState(
        settings=settings,
        build_agent=lambda s: build_agent(s, local_embedder=local),
        check_key=_check_key,
        warm_up=local.load,
        repo_root=_repo_root(),
    )
    try:
        load_thresholds(settings.embedding_model)
    except NotCalibratedError as exc:
        print(f"No se puede iniciar Morpho: {exc}", file=sys.stderr)
        return 2
    port = _free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    print(f"Morpho está en {url} (Ctrl+C para salir).")
    if not settings.has_api_key:
        print("Sin ANTHROPIC_API_KEY en .env: la página te deja pegar una key.")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(create_app(state), host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
