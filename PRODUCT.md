# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static HTML/CSS/JS, no build step (`dashboard/index.html`, `cargar.html`,
`estilo.css`), served by a local Flask server (`Makers/servidor.py`, bound to
127.0.0.1:5050). The page renders `dashboard/datos.json`, a snapshot the server
rewrites after every upload or review; it never queries the database directly.
All periods are precomputed in that snapshot, so switching months makes no
request. The server is local by design: exposing it would let anyone spend the
holder's Ollama and Groq.

## Users

**Primary: the account holder**, reviewing their own finances with the tool for
real. They open it to answer "where did my money go this month" and to see what
the system could not classify with confidence.

**Secondary: a project evaluator**, who judges the work by watching it function
as a real product. The evaluator is served by the same design, not by a separate
showcase mode: the proof is that it works as a tool, not that it explains itself.

## Product Purpose

Turns bank statements (text, CSV, or PDF, with or without a password) into
structured, validated, categorized financial data, and presents it back as an
understandable picture of the person's money, month by month, with a written
reading of each period and an assistant that answers questions about it.

Success is the account holder understanding their period at a glance — balance,
where the money went, what stands out — and trusting the numbers because the
system is explicit about what it was unsure of.

## Positioning

Two things a neighboring tool could not truthfully copy:

1. **The client's name never reaches the cloud.** A local model (qwen3:8b via
   Ollama) reads the original text. Names are masked before anything is sent to
   Groq. The counterparty is deliberately preserved — "Netflix" classifies,
   "Net****" does not — while the client's own name is masked.
2. **The system admits uncertainty instead of inventing.** When a movement is
   ambiguous or incomplete, it is flagged with `requiere_revision_humana` and a
   reason from a closed set of five, rather than being silently guessed.

A third, load-bearing for the dashboard: **the LLM never calculates.** Every
figure shown comes from SQL over SQLite. The model only writes prose about
numbers already computed. This is what makes the dashboard auditable.

## Operating Context

The account holder drags statements onto the upload page and watches them
processed row by row (local extraction takes ~20 s per movement on an M4 with
16 GB). Then they read the statement, switch months, resolve flagged cases, and
ask questions. Each month's reading is written by Groq the first time it is
opened and reused until its figures change; after a review it is marked stale
and rewritten only on request.

They use it on **laptop and phone, both for real** — personal finances get
checked from the phone, so mobile is a designed target, not a degraded fallback.

## Capabilities and Constraints

- **No login, no multi-user.** The only edits are review decisions: confirm,
  discard, mark duplicate or not, correct amount/currency/type/category/date,
  and undo. They are stored apart from what the pipeline extracted, applied by
  SQL views, and change the real totals. Corrected categories become RAG
  examples.
- **Pending cases count, with a warning.** Until resolved, a flagged movement
  is included in totals and the view states how much money is unconfirmed.
- **PDF passwords live only in memory.** Never stored or logged.
- **One client per snapshot.** The exported JSON covers a single `cliente_id`.
- **Eleven categories**, closed set: alimentacion, transporte, entretenimiento,
  vivienda, salud, educacion, compras, servicios, transferencia_persona,
  ingreso_laboral, otros.
- **Five revision reasons**, closed set: posible_intento_de_manipulacion,
  posible_duplicado, datos_insuficientes, moneda_no_especificada,
  formato_numerico_ambiguo. Multiple reasons arrive comma-separated.
- **Currencies never sum together.** Every aggregate is per currency; the
  snapshot names a `moneda_principal`. Eight currencies are permitted; the demo
  data is COP only.
- **Undated movements are kept, not dropped.** They land in a `sin_fecha`
  bucket so the page can say how many fell outside the time analysis.
- **The counterparty field flips by type.** In an ingreso it is
  `nombre_remitente`; in an egreso it is `nombre_destinatario`. The other field
  holds the masked client name. A table that picks one field shows asterisks in
  half its rows.
- **Anomaly detection is orientative, not proof.** It flags movements ≥2 standard
  deviations above the client's own mean for that type and currency, and the
  outlier inflates that deviation, so two similar extremes can mask each other.
- **The revision queue is both a trust signal and actionable.** It shows where
  the system was unsure, and the holder resolves it in place. Present without
  dominating. Discarded movements stay in the ledger, struck through.

## Brand Commitments

Project name: **Jhan y Jhon** (repository `Jhan-and-Jhon`). No logo, colors,
typography, or visual assets exist yet — none are committed.

## Evidence on Hand

- `dashboard/datos.json` — whatever the holder last processed. It contains
  amounts, dates, and counterparties in clear; never publish a real one.
- `ejemplos/` — synthetic statements authored to exercise the pipeline. They
  are not a real person's finances. Future work must not present them as real.
- PDF reading has only been tested on generated PDFs; real NuBank statements
  are the next calibration.
- `docs/guia_del_codigo.txt` — the code guide.
- No customers, benchmarks, pricing, or testimonials exist. Do not invent them.

## Product Principles

1. **The numbers are auditable or they are worthless.** Every figure traces to
   SQL. The LLM writes prose, never arithmetic.
2. **Admitted uncertainty beats a confident guess.** Surfacing what the system
   could not classify is a feature, and hiding it would betray the product.
3. **Privacy is structural, not a setting.** Masking happens before the network
   call, in code, not by asking a model to be discreet.
4. **The account holder came to understand their money**, not to admire a
   pipeline. Technical sophistication earns its place by making the money
   clearer, never by explaining itself.

## Accessibility & Inclusion

No product-specific standard was established. Amounts and categories must never
be distinguishable by color alone — ingreso/egreso carries a textual or
positional cue in addition to green/red.
