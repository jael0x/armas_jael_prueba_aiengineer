"use strict";

const $ = (id) => document.getElementById(id);
const state = { status: null, conversationId: null, busy: false, selected: null };

const PATH_TONE = {
  answered: "ok",
  escalated: "human",
  replaced: "warm",
  refused: "warm",
  abstained: "partial",
  asked_refund_amount: "partial",
  asked_order_id: "partial",
  empty: "plain",
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Error ${response.status}`);
  return data;
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "text") node.textContent = value;
    else if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
}

// --- status

async function refreshStatus() {
  try {
    state.status = await api("/api/status");
  } catch (error) {
    setPill("pill-key", "Servidor no disponible", "bad");
    return;
  }
  renderStatus();
  if (state.status.embedder === "loading" || state.status.tests_running) {
    setTimeout(refreshStatus, 2000);
  }
}

function setPill(id, text, tone) {
  const pill = $(id);
  pill.textContent = text;
  pill.dataset.state = tone || "";
}

function renderStatus() {
  const s = state.status;
  setPill("pill-model", `Modelo: ${s.model}`, "ok");
  if (s.embedder === "loading") {
    setPill("pill-embedder", "Embeddings: preparando EmbeddingGemma (1.2 GB la primera vez)…", "busy");
  } else if (s.embedder === "error") {
    setPill("pill-embedder", "Embeddings: error al cargar el modelo", "bad");
    $("pill-embedder").title = s.embedder_error || "";
  } else {
    const tau = s.tau === null ? "" : ` · τ ${s.tau.toFixed(3)}`;
    setPill("pill-embedder", `Embeddings: EmbeddingGemma listo${tau}`, "ok");
  }
  if (!s.has_key) setPill("pill-key", "Falta la key", "bad");
  else setPill("pill-key", s.key_source === "ui" ? "Key: pegada en esta sesión" : "Key: desde .env", "ok");

  $("key-setup").hidden = s.has_key;
  $("composer").hidden = !s.has_key;
  $("scenarios").hidden = !s.has_key;
  const note = $("composer-note");
  note.hidden = !(s.has_key && s.embedder === "loading");
  note.textContent = "Las preguntas nuevas esperan a que termine de cargar el modelo de embeddings.";

  const run = $("run-tests");
  run.disabled = !s.has_key || !s.tests_available || s.tests_running;
  if (!s.tests_available) showTestsError("Las pruebas en vivo solo corren desde una copia del repositorio.");
  else if (!s.has_key) showTestsError("Agrega la API key en la pestaña Chat para correr las pruebas en vivo.");
  else $("tests-error").hidden = true;
  $("live-command").textContent = s.live_tests_command;
}

// --- key

$("key-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("key-input");
  const button = $("key-submit");
  $("key-error").hidden = true;
  button.disabled = true;
  button.textContent = "Verificando…";
  try {
    state.status = await api("/api/key", { method: "POST", body: JSON.stringify({ key: input.value }) });
    input.value = "";
    newConversation();
    renderStatus();
    $("input").focus();
  } catch (error) {
    $("key-error").textContent = error.message;
    $("key-error").hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = "Usar esta key";
  }
});

// --- chat

function newConversation() {
  state.conversationId = null;
  state.selected = null;
  $("messages").replaceChildren($("empty-hint") || el("li", { class: "hint", id: "empty-hint" }));
  $("empty-hint").hidden = false;
  $("details").replaceChildren(
    el("p", { class: "muted", text: "Envía un mensaje para ver el camino del turno." })
  );
}

$("new-chat").addEventListener("click", () => {
  newConversation();
  $("input").focus();
});

$("composer").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = $("input").value;
  if (!text.trim() || state.busy) return;
  $("input").value = "";
  send(text);
});

$("input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("composer").requestSubmit();
  }
});

async function send(text) {
  state.busy = true;
  $("send").disabled = true;
  $("empty-hint").hidden = true;
  const list = $("messages");
  list.append(el("li", { class: "msg user" }, el("div", { class: "bubble", text })));
  const pending = el("li", { class: "msg morpho pending" }, el("div", { class: "bubble", text: "Morpho está escribiendo…" }));
  list.append(pending);
  pending.scrollIntoView({ block: "end", behavior: "smooth" });
  try {
    const turn = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ conversation_id: state.conversationId, message: text }),
    });
    state.conversationId = turn.conversation_id;
    const item = morphoMessage(turn);
    pending.replaceWith(item);
    select(item, turn);
    item.scrollIntoView({ block: "end", behavior: "smooth" });
  } catch (error) {
    pending.replaceWith(
      el("li", { class: "msg morpho failed" }, el("div", { class: "bubble", text: error.message }))
    );
  } finally {
    state.busy = false;
    $("send").disabled = false;
    $("input").focus();
  }
}

function morphoMessage(turn) {
  const bubble = el("button", { class: "bubble", type: "button", "aria-label": "Ver qué pasó en este turno" });
  bubble.append(...richText(turn.answer));
  const meta = el("div", { class: "meta" }, [
    el("span", { text: turn.path_label }),
    el("span", { text: "·" }),
    el("span", { text: turn.llm_requests ? `${turn.llm_requests} llamada(s) al modelo` : "sin modelo" }),
    el("span", { text: "·" }),
    el("span", { text: `${(turn.latency_ms / 1000).toFixed(1)} s` }),
  ]);
  const item = el("li", { class: `msg morpho${turn.path === "escalated" ? " human" : ""}` }, [bubble, meta]);
  bubble.addEventListener("click", () => select(item, turn));
  return item;
}

// Citations [DocN] and handoff references ESC-... are highlighted; everything else is plain text.
function richText(text) {
  const parts = [];
  const pattern = /(\[Doc\d+\]|ESC-\d{8}-[0-9A-F]{4})/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push(document.createTextNode(text.slice(last, match.index)));
    const token = match[0];
    parts.push(el("span", { class: token.startsWith("[") ? "doc" : "ref", text: token }));
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(document.createTextNode(text.slice(last)));
  return parts;
}

function select(item, turn) {
  if (state.selected) state.selected.classList.remove("selected");
  state.selected = item;
  item.classList.add("selected");
  renderDetails(turn);
}

// --- turn details

function section(label, ...content) {
  return el("div", { class: "section" }, [el("p", { class: "label", text: label }), ...content]);
}

function rows(items) {
  return el("ul", { class: "rows" }, items.map((item) => el("li", { class: "row" }, item)));
}

function renderDetails(turn) {
  const tau = state.status && state.status.tau;
  const usedModel = turn.llm_requests > 0;
  const blocks = [
    section(
      "Camino",
      el("span", { class: `status ${PATH_TONE[turn.path] || "plain"}`, text: turn.path_label }),
      el("p", { class: "muted small", text: `path = ${turn.path} · idioma = ${turn.language}` })
    ),
    section(
      "Reglas de escalamiento",
      turn.reasons.length
        ? rows(turn.reasons.map((r) => [el("strong", { text: r.label }), ` (${r.id})`]))
        : el("p", { class: "muted small", text: "Ninguna se activó." })
    ),
  ];
  if (turn.handoff) {
    blocks.push(
      section(
        "Handoff a un asesor",
        rows([
          [el("span", { class: "ref", text: turn.handoff.reference })],
          [el("span", { class: "muted", text: "Resumen redactado: " }), turn.handoff.summary],
        ])
      )
    );
  }
  blocks.push(section("Documentos recuperados", documents(turn, tau, usedModel)));
  blocks.push(
    section(
      "Consulta de pedidos",
      turn.lookups.length
        ? rows(turn.lookups.map(lookupRow))
        : el("p", { class: "muted small", text: "No se consultó ningún pedido." })
    )
  );
  blocks.push(
    section(
      "Validador de salida",
      !usedModel
        ? el("p", { class: "muted small", text: "No aplica: la respuesta es un texto fijo." })
        : turn.validation_problems.length
          ? rows(turn.validation_problems.map((p) => [`El borrador ${p}: se envió un texto fijo.`]))
          : el("p", { class: "small", text: "Aprobó el borrador del modelo." })
    )
  );
  blocks.push(
    section(
      "Costo y latencia",
      el("div", { class: "numbers" }, [
        number(turn.llm_requests, "llamadas al modelo"),
        number(`${(turn.latency_ms / 1000).toFixed(2)} s`, "latencia del turno"),
        number(`${turn.input_tokens} / ${turn.output_tokens}`, "tokens de entrada / salida"),
        number(`USD ${turn.cost_usd.toFixed(4)}`, "costo del turno"),
      ])
    )
  );
  $("details").replaceChildren(...blocks);
}

function documents(turn, tau, usedModel) {
  if (turn.retrieved.length) {
    // Bars are scaled to a cosine of 1; the dark mark is the threshold τ.
    const list = rows(
      turn.retrieved.map((hit) => {
        const fill = el("span");
        fill.style.width = `${Math.min(100, hit.score * 100)}%`;
        const bar = el("div", { class: "bar" }, fill);
        if (tau !== null) {
          const mark = el("i");
          mark.style.left = `${tau * 100}%`;
          bar.append(mark);
        }
        return [
          el("div", { class: "score" }, [
            el("span", {}, [el("span", { class: "doc", text: hit.doc_id }), ` ${hit.title}`]),
            el("strong", { text: hit.score.toFixed(3) }),
            bar,
          ]),
        ];
      })
    );
    if (tau !== null) {
      list.append(el("li", { class: "muted small", text: `La raya marca el umbral τ = ${tau.toFixed(3)}.` }));
    }
    return list;
  }
  const text =
    turn.path === "abstained" || turn.path === "refused"
      ? `Ningún documento superó τ${tau === null ? "" : ` = ${tau.toFixed(3)}`}; no se llamó al modelo.`
      : usedModel
        ? "No hizo falta: la pregunta trae un ID de pedido."
        : "No hizo falta: el turno se resolvió con reglas y textos fijos.";
  return el("p", { class: "muted small", text });
}

function lookupRow(result) {
  if (result.encontrado) {
    const eta = result.entrega_estimada ? `, entrega estimada ${result.entrega_estimada}` : ", sin entrega estimada";
    return [el("strong", { text: result.order_id }), ` → ${result.producto}, ${result.estado}${eta}`];
  }
  const why = result.error === "formato_invalido" ? "formato de ID inválido" : "no encontrado";
  return [el("strong", { text: String(result.order_id ?? "") }), ` → ${why}`];
}

function number(value, label) {
  return el("div", {}, [el("b", { text: String(value) }), el("span", { text: label })]);
}

// --- scenarios

async function loadScenarios() {
  const items = await api("/api/scenarios").catch(() => []);
  $("scenarios").replaceChildren(
    ...items.map((item) => {
      const chip = el("button", { type: "button", class: "chip", title: item.text, text: item.label });
      chip.addEventListener("click", () => {
        if (!state.busy) send(item.text);
      });
      return chip;
    })
  );
}

// --- live tests

function showTestsError(message) {
  $("tests-error").textContent = message;
  $("tests-error").hidden = false;
}

$("run-tests").addEventListener("click", async () => {
  const output = $("tests-output");
  const summary = $("tests-summary");
  $("run-tests").disabled = true;
  $("tests-error").hidden = true;
  output.hidden = false;
  output.textContent = "";
  summary.hidden = false;
  summary.className = "badge busy";
  summary.textContent = "Corriendo…";
  try {
    const response = await fetch("/api/tests/live", { method: "POST" });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || `Error ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      output.textContent += decoder.decode(value, { stream: true });
      output.scrollTop = output.scrollHeight;
    }
    const passed = output.textContent.match(/(\d+) passed/);
    const failed = output.textContent.match(/(\d+) (?:failed|error)/);
    const exit = output.textContent.match(/\[exit (-?\d+)\]/);
    const ok = exit && exit[1] === "0";
    summary.className = `badge ${ok ? "ok" : "bad"}`;
    summary.textContent = ok
      ? `${passed ? passed[1] : 0} pasaron`
      : `${failed ? failed[1] : "Algunas"} fallaron${passed ? `, ${passed[1]} pasaron` : ""}`;
  } catch (error) {
    summary.hidden = true;
    showTestsError(error.message);
  } finally {
    refreshStatus();
  }
});

// --- tabs

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => showTab(tab));
  tab.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const tabs = [...document.querySelectorAll(".tab")];
    const next = tabs[(tabs.indexOf(tab) + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
    showTab(next);
    next.focus();
  });
}

function showTab(active) {
  for (const tab of document.querySelectorAll(".tab")) {
    const selected = tab === active;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $(tab.getAttribute("aria-controls")).hidden = !selected;
  }
}

refreshStatus();
loadScenarios();
