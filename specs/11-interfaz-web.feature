# language: es
Característica: Interfaz web para probar a Morpho
  Como evaluador de la prueba técnica
  Quiero abrir una página local, conversar con Morpho y correr las pruebas en vivo
  Para revisar el sistema completo sin usar la terminal más que para iniciarlo

  Escenario: Un solo comando levanta la interfaz
    Cuando el evaluador corre "uv run morpho-ui"
    Entonces la interfaz queda disponible solo en 127.0.0.1
    Y se abre en el navegador

  Escenario: Sin key, la interfaz explica cómo agregarla y no deja conversar
    Dado que no hay una API key de Anthropic en .env
    Cuando el evaluador abre la interfaz
    Entonces la interfaz explica cómo crear .env o pegar la key
    Y el chat no envía mensajes

  Escenario: Una key pegada se usa sin guardarse
    Cuando el evaluador pega una key que Anthropic acepta
    Entonces Morpho queda listo para conversar
    Y la key no se escribe en disco ni vuelve en ninguna respuesta de la interfaz

  Escenario: Una key que Anthropic rechaza no se usa
    Cuando el evaluador pega una key que Anthropic rechaza
    Entonces la interfaz dice que la key no es válida
    Y Morpho sigue sin key

  Escenario: Cada respuesta muestra qué pasó en el turno
    Dado que el evaluador escribe "¿Cómo va mi pedido ORD-1001?"
    Cuando Morpho responde
    Entonces la interfaz muestra el camino del turno, la consulta del pedido y el resultado del validador
    Y muestra las llamadas al modelo, los tokens, el costo y la latencia

  Escenario: Un escalamiento muestra el motivo y la referencia de handoff
    Dado que el evaluador escribe "Quiero hablar con un asesor"
    Cuando Morpho responde
    Entonces la interfaz muestra el motivo "solicitud de asesor"
    Y muestra la misma referencia de handoff que recibió el cliente

  Escenario: Los escenarios rápidos salen del golden set
    Cuando el evaluador elige un escenario rápido
    Entonces se envía el mismo mensaje que usa la evaluación

  Escenario: Las pruebas en vivo se corren desde la interfaz
    Dado que hay una API key de Anthropic
    Cuando el evaluador corre las pruebas en vivo
    Entonces la interfaz muestra la salida de pytest mientras corre
    Y al final dice cuántas pruebas pasaron

  Escenario: El modelo de embeddings se prepara al iniciar
    Cuando la interfaz arranca
    Entonces carga EmbeddingGemma en segundo plano, descargándolo la primera vez
    Y muestra si está listo o si falló la carga
