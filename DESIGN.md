# DESIGN.md: identidad visual de Morpho

Morpho es el agente de soporte de TiendaHogar. Este documento fija cómo se ve todo lo que muestra al agente: diagramas de arquitectura, páginas de documentación en HTML y una futura interfaz de chat. El código del agente no depende de este archivo.

La paleta sale de una maqueta de referencia ("Modern Intelligent Workspace"): fondo casi blanco, tarjetas blancas muy redondeadas, texto en grises pizarra, un solo acento morado y degradados suaves de morado a rosa y de rosa a naranja. El modo oscuro no estaba en la referencia: se deriva aquí con las mismas reglas de contraste.

---

## 1. Principios

1. **Un solo acento.** El morado (`purple-600`) marca lo que es Morpho y lo que se puede tocar. Los demás colores comunican estado.
2. **Superficies claras y aire.** Fondo `#FAFAFA`, tarjetas blancas, bordes casi invisibles y sombras difusas. La jerarquía la dan el tamaño del texto y el espacio, no las líneas.
3. **El color nunca va solo.** Todo estado (definido, parcial, por definir, escalado) lleva también texto o forma. Así se lee en escala de grises y con daltonismo.
4. **Rosa y naranja son el camino humano.** Se reservan para escalamientos, alertas y la ruta hacia un asesor. No se usan como decoración en zonas de contenido normal.
5. **Movimiento lento y opcional.** Flotación y pulso suaves; con `prefers-reduced-motion` todo queda quieto.

---

## 2. Paleta (modo claro)

Los valores coinciden con la escala de Tailwind. El contraste está medido según WCAG 2.x contra el fondo indicado.

### 2.1 Neutros

| Token | Hex | Uso | Contraste |
|---|---|---|---|
| `--bg` | `#FAFAFA` | Fondo de página | n/a |
| `--surface` | `#FFFFFF` | Tarjetas, paneles, cajas | n/a |
| `--surface-2` | `#F8FAFC` (slate-50) | Filas, zonas hundidas | n/a |
| `--line` | `#F1F5F9` (slate-100) | Borde de tarjetas (decorativo) | 1.10 sobre blanco |
| `--line-2` | `#E2E8F0` (slate-200) | Separadores, barras de esqueleto | 1.23 sobre blanco |
| `--dot` | `#E5E7EB` (gray-200) | Patrón de puntos | decorativo |
| `--ink` | `#0F172A` (slate-900) | Títulos y texto principal | 17.85 sobre blanco |
| `--ink-2` | `#1E293B` (slate-800) | Texto en pastillas | n/a |
| `--ink-3` | `#334155` (slate-700) | Texto secundario fuerte | 10.35 sobre blanco |
| `--muted` | `#64748B` (slate-500) | Texto de apoyo, flechas | 4.76 sobre blanco, 4.56 sobre `--bg` |
| `--faint` | `#94A3B8` (slate-400) | Íconos decorativos | 2.56: nunca para texto |

### 2.2 Acento de marca

| Token | Hex | Uso | Contraste |
|---|---|---|---|
| `--primary` | `#9333EA` (purple-600) | Marca, botones, sistema en foco, enlaces | 5.38 sobre blanco; blanco sobre él: 5.38 |
| `--primary-strong` | `#7E22CE` (purple-700) | Hover y texto morado pequeño | 6.98 sobre blanco |
| `--primary-edge` | `#A855F7` (purple-500) | Borde de cajas interactivas | 3.96 (cumple 3:1 de UI) |
| `--primary-200` | `#E9D5FF` | Líneas de conexión suaves | decorativo |
| `--primary-100` | `#F3E8FF` | Halo de hover, fondos de chip | decorativo |
| `--primary-50` | `#FAF5FF` | Fondo de ícono en círculo | `--primary` sobre él: 5.02 |
| `--primary-glow` | `rgba(192,132,252,0.20)` (purple-400/20) | Brillo difuso detrás de ilustraciones | decorativo |

### 2.3 Degradados

| Token | Valor | Uso |
|---|---|---|
| `--grad-brand` | `linear-gradient(90deg, #D8B4FE, #F0ABFC, #FDA4AF)` (purple-300, fuchsia-300, rose-300) | Borde de 1 px de la pastilla de marca y del sistema en foco |
| `--grad-human` | `linear-gradient(90deg, #FDA4AF, #FDBA74)` (rose-300, orange-300) | Borde de la pastilla de escalamiento |
| `--grad-warm` | `linear-gradient(90deg, #FED7AA, #FECDD3)` (orange-200, rose-200) | Acentos cálidos secundarios |
| `--grad-fade-rose` | `linear-gradient(180deg, #FFF1F2, transparent)` (rose-50) | Cabecera de tarjeta de alerta |

### 2.4 Estados y camino humano

Los colores de relleno (400 y 500) son decorativos en modo claro. El texto usa siempre el tono 600 o 700.

| Estado | Relleno | Texto | Contraste del texto |
|---|---|---|---|
| Definido | `#34D399` (emerald-400) | `#047857` (emerald-700) | 5.48 |
| Parcial | `#FBBF24` (amber-400) | `#B45309` (amber-700) | 5.02 |
| Por definir | `#FB7185` (rose-400) | `#E11D48` (rose-600) | 4.70 |
| Escalado a humano | `#F43F5E` (rose-500) | `#E11D48` (rose-600) | 4.70 |
| Advertencia cálida | `#F97316` (orange-500) | `#C2410C` (orange-700) | 5.18 |

`rose-500` sobre blanco da 3.67 y `orange-500` da 2.80: sirven para íconos grandes y rellenos, no para texto menor a 18.66 px en negrita.

### 2.5 Acentos de íconos

Solo para íconos sueltos dentro de ilustraciones: `#2563EB` (blue-600), `#16A34A` (green-600), `#DC2626` (red-600), `#4F46E5` (indigo-600). No forman parte de la paleta de estados.

---

## 3. Modo oscuro (derivado)

Se activa con `prefers-color-scheme: dark` o con `data-theme="dark"` en `<html>`. Mantiene la misma lógica: un acento, estados con texto.

| Token | Hex | Contraste |
|---|---|---|
| `--bg` | `#0C0A12` | n/a |
| `--surface` | `#16131F` | n/a |
| `--surface-2` | `#1D1928` | n/a |
| `--line` / `--line-2` | `#2A2536` / `#352F45` | decorativo |
| `--ink` | `#F1F5F9` | 16.71 sobre `--surface` |
| `--muted` | `#A1A1B5` | 7.22 sobre `--surface` |
| `--primary` (texto y bordes) | `#C084FC` (purple-400) | 6.93 sobre `--surface` |
| `--primary-fill` | `#9333EA` con texto blanco | 5.38 |
| Definido / Parcial / Por definir | `#34D399` / `#FBBF24` / `#FB7185` | 9.52 / 10.97 / 6.80 |
| Advertencia cálida | `#FB923C` | 8.09 |

El fondo animado (sección 6) usa en oscuro tonos `#120F1C`, `#1E1530` y `#24121A` a la misma opacidad.

---

## 4. Tipografía

- **Familia:** pila del sistema, con Inter primero si está instalada: `Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`. Monoespaciada: `ui-monospace, "SF Mono", Menlo, Consolas, monospace`.
- **Títulos:** peso 500 a 600, `letter-spacing: -0.01em` (tracking-tight).
- **Escala:**

| Rol | Tamaño / interlineado | Peso |
|---|---|---|
| Título de página | 30 a 48 px / 1.1 | 600 |
| Título de tarjeta | 20 px / 28 px | 500 |
| Título de caja de diagrama | 16 px / 20 px | 600 |
| Cuerpo | 16 px / 24 px | 400 |
| Texto de apoyo | 14 px / 20 px | 400, color `--muted` |
| Etiqueta en mayúsculas | 12 px / 16 px, `letter-spacing: 0.12em` | 500 |
| Código y tecnología | 12 px mono | 400 |

- Selección de texto: fondo `#E9D5FF` y texto `#581C87` (purple-200 y purple-900).

---

## 5. Forma, espacio y superficies

| Token | Valor | Uso |
|---|---|---|
| `--r-card` | 32 px (2rem) | Tarjetas grandes y paneles |
| `--r-inner` | 16 px | Áreas de ilustración, ventanas, cajas de diagrama |
| `--r-row` | 12 px | Filas, chips grandes |
| `--r-chip` | 8 px | Etiquetas pequeñas, cuadros de ícono |
| `--r-pill` | 999 px | Pastillas, botones de nivel |
| `--shadow-card` | `0 8px 30px rgba(0,0,0,0.04)` | Reposo |
| `--shadow-lift` | `0 20px 40px -10px rgba(0,0,0,0.08)` | Hover de tarjeta (sube 5 px) |
| `--shadow-pill` | `0 10px 25px -5px rgba(147,51,234,0.10)` | Pastilla de marca |

- **Espaciado:** base de 4 px. Padding de tarjeta 32 a 40 px; separación entre tarjetas 24 px.
- **Patrón de puntos:** `radial-gradient(var(--dot) 1px, transparent 1px)` con `background-size: 20px 20px`. Va detrás de diagramas e ilustraciones, nunca detrás de texto largo.
- **Vidrio:** `background: rgba(255,255,255,0.7); backdrop-filter: blur(12px)` con borde `rgba(255,255,255,0.4)`. Solo para elementos flotantes pequeños.
- **Pastilla con borde degradado:** contenedor con `padding: 1px` y `--grad-brand` de fondo; adentro, superficie blanca al 95% con `border-radius` igual.
- **Ícono en círculo:** 36 px, fondo `--primary-50`, borde `--primary-100`, ícono `--primary`.

---

## 6. Movimiento y fondo

| Efecto | Definición | Uso |
|---|---|---|
| Flotar | `translateY(-6px)`, 2.5 s, `ease-in-out`, ida y vuelta, desfase aleatorio | Pastillas e íconos de ilustración |
| Pulso | `scale(1.05)`, 2 s, `ease-in-out`, ida y vuelta | Un solo elemento de estado activo |
| Entrada | sube 40 px y aparece, 0.8 s, `cubic-bezier(0.2, 0, 0, 1)`, escalonado 0.15 s | Tarjetas al cargar |
| Hover de tarjeta | sube 5 px, 0.3 s, `--shadow-lift` | Tarjetas interactivas |
| Presión | `scale(0.98)`, 120 ms | Botones |

**Aura de fondo:** un canvas WebGL a pantalla completa, al 35% de opacidad y sin eventos de puntero, mezcla tres tonos con ondas lentas (`t * 0.2`): `#FAFAFF`, `#EDE6FA` (morado muy suave) y `#FFF0F0` (rosa melocotón). Si WebGL no está disponible, el fondo queda en `--bg`.

Con `prefers-reduced-motion: reduce` se desactivan flotación, pulso y entrada, y el aura dibuja un solo cuadro estático.

---

## 7. Iconografía

- La referencia usa el set **Solar** (Iconify), en variantes `linear` para la interfaz y `bold-duotone` para ilustraciones, a 14, 16, 18 o 20 px.
- En páginas autocontenidas (diagramas, artefactos) los íconos van como SVG en línea con `stroke: currentColor` y trazo de 1.5 px, para no depender de un CDN.
- **Marca:** una mariposa simple (dos alas en `--grad-brand` sobre un cuadro `--primary` de 8 px de radio). Morpho es un género de mariposas.

---

## 8. Mapeo semántico para diagramas C4

| Elemento C4 | Fondo | Texto | Borde / forma |
|---|---|---|---|
| Persona | `--ink` (`#0F172A`) | blanco (17.85) | Esquinas superiores de 40 px |
| Sistema en foco (Morpho) | `--primary` | blanco (5.38) | Anillo `--grad-brand` de 2 px |
| Sistema externo | `#475569` (slate-600) | blanco (7.58) | Sin borde extra |
| Contenedor o componente | `--surface` | `--ink` | 2 px `--primary-edge` (3.96) |
| Almacén de datos | `--surface` | `--ink` | Radio elíptico y borde superior de 6 px |
| Fuera del flujo (tests, evaluación) | transparente | `--ink` | 2 px discontinuo `--muted` |
| Spec | `--surface` | `--ink` | Barra izquierda de 6 px en el color del estado |
| Relación | n/a | `--muted` | Línea discontinua 1.4 px `--muted` (4.56) |
| Relación resaltada | n/a | `--ink` | Línea continua 2.2 px `#E11D48` |
| Límite del sistema | n/a | `--muted` | 2 px discontinuo, radio 18 px |

En oscuro: persona `#E2E8F0` con texto `#0F172A` (14.48), externo `#334155` con texto `#F1F5F9` (9.45), bordes de caja `#C084FC` (6.93).

---

## 9. Accesibilidad

- Texto normal: contraste mínimo 4.5:1. Bordes de controles y gráficos con significado: 3:1.
- Controles de al menos 44 px de alto; foco visible con `outline: 2px solid var(--primary)` y 2 px de separación.
- Nada se comunica solo con color ni solo con movimiento.
- Etiquetas en español; `lang="es"` en el documento.

---

## 10. Tokens CSS

```css
:root {
  --bg: #FAFAFA; --surface: #FFFFFF; --surface-2: #F8FAFC;
  --line: #F1F5F9; --line-2: #E2E8F0; --dot: #E5E7EB;
  --ink: #0F172A; --ink-2: #1E293B; --ink-3: #334155; --muted: #64748B; --faint: #94A3B8;
  --primary: #9333EA; --primary-strong: #7E22CE; --primary-edge: #A855F7;
  --primary-200: #E9D5FF; --primary-100: #F3E8FF; --primary-50: #FAF5FF;
  --primary-glow: rgba(192, 132, 252, 0.20);
  --grad-brand: linear-gradient(90deg, #D8B4FE, #F0ABFC, #FDA4AF);
  --grad-human: linear-gradient(90deg, #FDA4AF, #FDBA74);
  --ok-fill: #34D399; --ok-ink: #047857;
  --partial-fill: #FBBF24; --partial-ink: #B45309;
  --open-fill: #FB7185; --open-ink: #E11D48;
  --human-fill: #F43F5E; --human-ink: #E11D48;
  --warm-fill: #F97316; --warm-ink: #C2410C;
  --person-bg: #0F172A; --person-ink: #FFFFFF;
  --external-bg: #475569; --external-ink: #FFFFFF;
  --arrow: #64748B; --hot: #E11D48;
  --r-card: 32px; --r-inner: 16px; --r-row: 12px; --r-chip: 8px; --r-pill: 999px;
  --shadow-card: 0 8px 30px rgba(0, 0, 0, 0.04);
  --shadow-lift: 0 20px 40px -10px rgba(0, 0, 0, 0.08);
  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --ease: cubic-bezier(0.2, 0, 0, 1);
  color-scheme: light;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0C0A12; --surface: #16131F; --surface-2: #1D1928;
    --line: #2A2536; --line-2: #352F45; --dot: #2A2536;
    --ink: #F1F5F9; --ink-2: #E2E8F0; --ink-3: #CBD5E1; --muted: #A1A1B5; --faint: #6B6880;
    --primary: #C084FC; --primary-strong: #D8B4FE; --primary-edge: #C084FC;
    --primary-200: #3B2A55; --primary-100: #2A2040; --primary-50: #1F1830;
    --ok-ink: #34D399; --partial-ink: #FBBF24; --open-ink: #FB7185; --human-ink: #FB7185; --warm-ink: #FB923C;
    --person-bg: #E2E8F0; --person-ink: #0F172A;
    --external-bg: #334155; --external-ink: #F1F5F9;
    --arrow: #8B8BA3; --hot: #FB7185;
    color-scheme: dark;
  }
}
/* Repetir el bloque oscuro bajo :root[data-theme="dark"] para el cambio manual. */
```

---

## 11. Sí y no

| Sí | No |
|---|---|
| Un acento morado por vista | Morado y rosa compitiendo en el mismo nivel |
| Rosa para el camino a un humano | Rosa como decoración de contenido normal |
| Estado con color y texto ("Por definir") | Un punto de color sin etiqueta |
| `rose-600` o `orange-700` para texto | `rose-500`, `orange-500` o `amber-400` como color de texto |
| Sombras de 4% a 8% | Sombras duras o bordes oscuros en tarjetas |
| Movimiento lento que se puede apagar | Animaciones que se repiten rápido o no respetan la preferencia del sistema |
