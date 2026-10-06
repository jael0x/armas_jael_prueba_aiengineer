# Morpho

Morpho es el agente de soporte al cliente de TiendaHogar. Responde preguntas con RAG sobre las cinco políticas de la tienda, consulta el estado de pedidos con la tool `consultar_estado_pedido` y deriva a un asesor humano lo que las políticas reservan a personas: reembolsos mayores a $500, quejas sobre el trato del personal, disputas de facturación y temas legales. No inventa datos: lo que no está en los documentos ni en la tabla de pedidos, no lo dice.

Las decisiones de arquitectura, RAG, pruebas y producción están en [SUBMISSION.md](SUBMISSION.md).

## Probarlo con un solo comando

Requisitos: [uv](https://docs.astral.sh/uv/getting-started/installation/) y una API key de Anthropic (Claude). uv descarga Python 3.12 si no lo tienes.

```bash
git clone https://github.com/jael0x/armas_jael_prueba_aiengineer.git
cd armas_jael_prueba_aiengineer
cp .env.example .env    # opcional: pega tu key en ANTHROPIC_API_KEY
uv run morpho-ui
```

`uv run morpho-ui` instala las dependencias, levanta la interfaz en `http://127.0.0.1:8000` y la abre en el navegador. Si no creaste `.env`, la página te deja pegar la key: queda solo en la memoria del servidor, no se escribe en disco y nunca vuelve al navegador.

En la interfaz:

- **Chat.** Escribe como cliente o toca un escenario rápido (garantías, pedidos, reembolsos, quejas, inyección, inglés). Al tocar una respuesta de Morpho, el panel "Qué pasó en el turno" muestra el camino que siguió, las reglas que se activaron, la referencia de handoff, los documentos recuperados con su score frente al umbral, los pedidos consultados, el veredicto del validador, los tokens, el costo y la latencia.
- **Pruebas en vivo.** Corre `pytest -m live` contra Claude y muestra la salida mientras corre.

La primera vez, el modelo de embeddings (EmbeddingGemma, 1.2 GB) se descarga en segundo plano; la cabecera muestra cuándo está listo. Las preguntas de los documentos y del set etiquetado ya tienen su vector en el caché del repositorio.

## Pruebas

```bash
uv run pytest tests/
```

315 pruebas en un segundo, sin red ni API key: el modelo se reemplaza por `FakeLLM` y los vectores salen del caché versionado (`src/morpho/retrieval/embeddings_cache.json`). Para correr solo los tres casos que pide el reto: `uv run pytest -m challenge`.

| Lo que pide el reto | Dónde está |
|---|---|
| El RAG trae el documento correcto para una pregunta clara | `tests/test_retrieval.py::test_clear_question_retrieves_its_document_first` ("¿Cuánto dura la garantía de una lavadora?" → Doc 1, con los vectores reales) |
| La tool responde bien con un ID válido y maneja uno inválido sin inventar datos | `tests/test_orders.py::test_order_in_transit_reports_product_status_and_estimated_delivery`, `::test_unknown_order_is_not_found_without_invented_data` y `::test_malformed_id_is_rejected_without_reading_the_orders` |
| El guardrail se activa | `tests/test_rules.py::test_case_reserved_for_people_is_escalated` y `tests/test_agent.py::test_case_reserved_for_people_is_escalated_without_the_model` (escala sin llamar al modelo) |

Otras pruebas, que sí usan la API de Claude:

```bash
uv run pytest -m live                       # 11 escenarios contra Claude (~25 s, ~USD 0.03)
uv run python -m morpho.evals.run_eval      # golden set de 55 casos con Claude como juez (~3 min, ~USD 0.32)
uv run python -m morpho.evals.run_eval --no-judge   # solo los chequeos en código (~USD 0.07)
```

El último reporte de la evaluación está en [evals/report.md](evals/report.md).

## Otras formas de usarlo

```bash
uv run morpho        # chat en la terminal; escribe "salir" para terminar
uv run morpho-mcp    # servidor MCP por stdio con la tool consultar_estado_pedido
npx @modelcontextprotocol/inspector uv run morpho-mcp   # probar el servidor MCP en MCP Inspector
```

Para regenerar el caché de vectores y el umbral de recuperación (corren en local, sin key):

```bash
uv run python -m morpho.evals.record_embeddings
uv run python -m morpho.evals.calibrate
```

## Variables de entorno

Se leen del entorno o de `.env` (ver [.env.example](.env.example)). Ninguna es obligatoria para correr las pruebas.

| Variable | Por defecto | Para qué |
|---|---|---|
| `ANTHROPIC_API_KEY` | (vacía) | Llamar a Claude desde el chat, la interfaz, las pruebas en vivo y la evaluación |
| `MORPHO_LLM_MODEL` | `claude-haiku-4-5` | Modelo del agente |
| `MORPHO_JUDGE_MODEL` | `claude-sonnet-5-5` | Modelo juez de la evaluación |
| `MORPHO_EMBEDDING_MODEL` | `google/embeddinggemma-300m` | Modelo de embeddings local |
| `MORPHO_EFFORT` | (vacía) | `effort` de Claude para modelos que lo aceptan; Haiku 4.5 no |
| `MORPHO_MODELS_DIR` | `~/.cache/fastembed` | Dónde se descarga el modelo de embeddings |
| `MORPHO_VAR_DIR` | `var` | Dónde se escriben los registros de handoff y las trazas |

## Sin uv

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e . pytest httpx
pytest tests/
```

## Estructura

```text
src/morpho/
  agent.py              orquesta cada turno
  guardrails/           normalización, montos, reglas de escalamiento, PII y validador de salida
  retrieval/            embeddings locales, caché de vectores, store y retriever con umbral
  llm/                  puerto LLMClient, adaptador de Claude y FakeLLM para pruebas
  tools/orders.py       consultar_estado_pedido y la tabla mock
  knowledge/            los cinco documentos de políticas, textuales
  prompts.py            prompt del sistema y textos fijos en español e inglés
  records.py            registro de handoffs y trazas por turno (JSONL, PII redactada)
  web/                  interfaz web (uv run morpho-ui)
  cli.py, mcp_server.py chat en terminal y servidor MCP
  evals/                golden set, juez, calibración del umbral y grabación del caché
tests/                  pruebas offline y en vivo
specs/                  escenarios en Gherkin (español) que cubren las pruebas
evals/                  último reporte de la evaluación
```

Los registros de cada conversación quedan en `var/handoffs.jsonl` y `var/traces.jsonl`.
