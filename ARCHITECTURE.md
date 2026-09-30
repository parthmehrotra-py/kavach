# Kavach — Technical Architecture Blueprint

## 1. Product contract

Kavach is a local-first Windows desktop web app that helps a user safely take text or a document to an external cloud AI and restore the AI response locally. The user pastes text or uploads a supported file; Kavach detects sensitive spans, replaces them with stable placeholders such as `[PERSON_1]`, and gives the user redacted text to copy. After the user pastes an AI response, Kavach restores placeholders from a session-local mapping.

### Release scope

- Windows on the developer's AMD x86-64 HP PC; Python CPU path is the required baseline.
- Optional AMD NPU experimentation only if the installed, documented runtime supports it. Do not make AMD NPU support a release dependency.
- A future, isolated Qualcomm Snapdragon/GenieX/QNN adapter may be scaffolded only after the CPU path works; label it unverified until exercised on actual Snapdragon hardware.
- Plain text, image OCR, and text-based PDF ingestion; synthetic sample documents only.
- India-aware detection: Aadhaar candidate with Verhoeff checksum, PAN, IFSC, UPI ID, Indian phone, PIN code, and configurable account-number patterns. Contextual person/address detection is optional and must degrade cleanly when no local model/runtime is available.
- Single-user local service and one HTML page. No accounts, cloud service, telemetry, phone app, multi-device support, or network dependency.

### Non-negotiable invariants

1. Original document text, detected values, and token map stay in process memory only. No persistence, logs, analytics, crash uploads, or external requests containing user content.
2. Redaction and restore are deterministic within a session. A placeholder maps to exactly one original span; repeated identical spans reuse a token by default. Tokens are opaque and collision-checked.
3. Restore changes only exact Kavach tokens present in the response. Unknown, malformed, or user-edited tokens remain untouched and are reported.
4. Detection is conservative: checksum validation is a confidence signal, never proof of identity. Display category and confidence/source; let the user inspect/edit detections before redacting.
5. Benchmark values are measured on the current device, identify the selected provider, and are never hard-coded or presented as Snapdragon measurements unless actually collected on Snapdragon hardware.
6. Network-off status means the app's own process made no network requests during the measured offline check. It must not imply that an external AI service is offline.
7. Never put real identifiers in repository samples, screenshots, tests, logs, or demo recordings.

## 2. Architecture and stack

### Runtime stack

- OS target: Windows 11; first development baseline: HP PC with AMD CPU, x86-64.
- Language: Python 3.11 or 3.12, pinned in setup documentation; choose a version with compatible native wheels before implementation.
- API: FastAPI + Uvicorn bound to `127.0.0.1` only.
- UI: one static semantic HTML page, CSS, and browser-native JavaScript; no frontend framework or build chain.
- Schemas: Pydantic request/response models; explicit size and type limits.
- OCR: RapidOCR with ONNX Runtime CPU provider as baseline. Provider selection is explicit and reported. Add AMD or Qualcomm provider only behind adapters and only when installed and verified. CPU fallback must always remain usable.
- PDF: PyMuPDF for text extraction; rasterize pages for OCR only when needed, with page and pixel limits.
- Images: Pillow for format validation, orientation normalization, and bounded resizing.
- Tests/quality: pytest, HTTPX/FastAPI TestClient, Ruff, and mypy (or pyright; choose one and pin it). All are development dependencies.
- Packaging/setup: PowerShell `setup.ps1`; local virtual environment; no administrator requirement. A suitable local model may be installed for the optional contextual-detection phase when that feature needs it. Document its exact source, license, size, runtime requirements, and installation step; never download it silently or commit its weights. Core setup and CPU workflow must not require the model.

### Component flow

```text
Browser (127.0.0.1)
  | text / bounded file upload
  v
FastAPI routes + input validation
  |------------------------------|
  v                              v
Text extraction/OCR          Detection pipeline
  |                              |-- India validators/patterns
  |                              |-- optional local contextual adapter
  |                              |-- merge, deduplicate, review spans
  |------------------------------|
                 v
        Session redaction engine
        | original spans + token map in RAM
        | redacted text returned to browser
                 v
        User's external AI (manual copy/paste; outside Kavach)
                 |
        pasted AI response
                 v
        Exact-token restore endpoint
                 |
        restored response + unresolved-token list
```

### API contract (versioned under `/api/v1`)

- `GET /api/v1/health`: readiness, app version, selected OCR/runtime provider, and whether optional local contextual model is available. No paths, secrets, or user content.
- `POST /api/v1/analyze`: JSON `{text: string}`; returns candidate spans `{id, category, start, end, value_preview, confidence, source, validator_status}`. Preview should be masked by default; full value is returned only if UI explicitly asks for reveal.
- `POST /api/v1/redact`: JSON containing source text and the user-approved candidate IDs; creates/reuses an in-memory session and returns `{session_id, redacted_text, replacements}`. Require explicit approval in UI.
- `POST /api/v1/restore`: JSON `{session_id, text}`; returns `{restored_text, restored_count, unresolved_tokens}`.
- `POST /api/v1/ingest`: multipart image or PDF; returns extracted text and page/OCR metadata for review, never redacts without confirmation.
- `POST /api/v1/benchmark`: runs a bounded local workload; returns measured elapsed times, provider names, workload size, and device/runtime labels. Benchmark cannot transmit or persist input.
- `DELETE /api/v1/session/{session_id}`: clear token map and session state immediately.

Use a random, unguessable session ID, strict localhost CORS/origin policy, request size limits, and session TTL. Do not enable wildcard CORS. Localhost is not an authentication boundary: reject non-loopback binds by default and document the threat model.

### Detection behavior

- Keep detection functions pure: input text plus configuration yields spans; no filesystem/network side effects.
- Preserve original offsets. Use Python Unicode code-point offsets consistently end-to-end; do not normalize source text after offsets are generated.
- Aadhaar: recognize allowed formatting, normalize digits for validation, require exactly 12 digits, reject known invalid leading patterns as applicable, and validate Verhoeff checksum. Keep validator implementation isolated and unit-test against published algorithm vectors plus synthetic examples.
- PAN: uppercase format `AAAAA9999A`; pattern match only, clearly state that format validation does not verify issuance.
- IFSC: pattern validation only; do not imply bank existence validation.
- UPI: handle common `handle@provider` form without claiming the handle is active.
- Phone: India-aware country/area formats with conservative boundaries; do not label arbitrary ten-digit numbers as verified phone ownership.
- PIN: six digits with India-aware boundary/context rule; avoid treating every six-digit value as a PIN.
- Account number: only detect with contextual cues or explicit user-added rule; do not claim checksum verification where none exists.
- Optional contextual pass: local-only, behind `ContextualDetector` interface, bounded input, cancellable timeout, and source attribution. It may add candidates but must never silently remove deterministic candidates. On unavailable/error/timeout, proceed with deterministic results and surface degraded status.
- Merge overlaps deterministically: explicit priority order, then longest span, then stable detector ID. UI can edit/ignore candidates before redaction.

### Session and failure policy

- In-memory session store only; enforce max sessions, per-session bytes, and TTL; no disk-backed fallback.
- Clear mappings on explicit delete, TTL expiry, server shutdown, and failed partial session creation.
- Token grammar must be unambiguous, e.g. `[[KAVACH:PERSON:0001]]`; escape or safely handle token-like source text before processing. Never interpret arbitrary user text as a token during restore.
- On parse/OCR/runtime failure, return a typed error with a safe user-readable message. Do not return stack traces or document contents in server logs.

## 3. Repository structure

```text
kavach/
├── ARCHITECTURE.md                 # this blueprint; implementation contract
├── README.md                       # setup, limitations, verified hardware table, demo
├── setup.ps1                       # ARM64/x64 detection, venv, pinned install, smoke check
├── pyproject.toml                  # pinned dependencies and tool configuration
├── .python-version                 # selected supported Python version
├── .gitignore                      # venv, caches, local models, uploads, outputs
├── src/
│   └── kavach/
│       ├── __init__.py
│       ├── main.py                 # app construction and localhost startup
│       ├── config.py               # limits, paths, provider settings
│       ├── api/
│       │   ├── routes.py           # thin HTTP handlers
│       │   ├── schemas.py          # Pydantic DTOs
│       │   ├── errors.py           # safe typed error mapping
│       │   └── security.py         # loopback, origin, upload guards
│       ├── core/
│       │   ├── models.py           # internal candidate/session models
│       │   ├── pipeline.py         # orchestration only
│       │   ├── merge.py            # overlap resolution and stable order
│       │   ├── redaction.py        # placeholder and offset-safe replacement
│       │   ├── restoration.py      # exact token restoration
│       │   └── session_store.py    # bounded in-memory TTL store
│       ├── detectors/
│       │   ├── base.py             # detector protocol
│       │   ├── aadhaar.py          # normalization + Verhoeff
│       │   ├── pan.py
│       │   ├── ifsc.py
│       │   ├── upi.py
│       │   ├── phone.py
│       │   ├── pin.py
│       │   ├── account.py
│       │   └── contextual.py       # optional adapter protocol/implementation
│       ├── ingest/
│       │   ├── service.py          # file validation and routing
│       │   ├── image_ocr.py        # RapidOCR wrapper
│       │   └── pdf_text.py         # text extraction and bounded OCR fallback
│       ├── hardware/
│       │   ├── capabilities.py     # conservative capability report
│       │   ├── providers.py        # explicit provider selection/fallback
│       │   └── benchmark.py        # measured local timings only
│       └── web/
│           ├── index.html          # single page UI
│           ├── app.js              # workflow and API calls
│           └── styles.css
├── tests/
│   ├── unit/
│   │   ├── test_aadhaar.py
│   │   ├── test_detectors.py
│   │   ├── test_merge.py
│   │   ├── test_redaction_restore.py
│   │   ├── test_session_store.py
│   │   └── test_hardware_fallback.py
│   ├── integration/
│   │   ├── test_api_flow.py
│   │   ├── test_ingest_limits.py
│   │   └── test_offline.py
│   └── fixtures/
│       ├── synthetic_text.txt
│       ├── synthetic_scan.png
│       └── synthetic_text.pdf
└── models/                          # ignored; user-provided/downloaded local models only
    └── README.md                    # model provenance, license, placement; no weights committed
```

Do not create modules outside this tree without updating this architecture first. Keep routes thin, core logic framework-independent, and hardware integrations optional.

## 4. Sequential implementation roadmap and QA gates

Kiro must complete tasks in order. Each task is a small reviewable change. Stop and repair a failed gate before beginning the next task. A task is complete only when its code, focused tests, and evidence satisfy every listed criterion. No benchmark claims without recorded measurements.

### Task 0 — Repository and dependency baseline

**Build:** Create only the initial project metadata, `.gitignore`, and minimal dependency/tool pins needed to start the app later. Confirm the developer's actual Python version and architecture before selecting pins. Add later-phase dependencies when their phase begins; do not install OCR/inference stacks, model runtimes, or weights during Phase 0.

**Do not build yet:** API behavior, detector logic, model downloads, UI, or accelerator setup.

**QA checklist:**
- [ ] `python --version` is within the selected supported range and architecture is reported.
- [ ] A fresh venv can install the small Phase 0 dependency set on the target HP Windows environment.
- [ ] One documented smoke check confirms the environment and declared core dependencies import successfully.
- [ ] Ruff and the chosen type checker are configured and can be invoked; do not add placeholder source files just to make them report a clean project.
- [ ] `.gitignore` excludes `.venv/`, caches, local model weights, uploaded files, and benchmark outputs.
- [ ] No credentials, real identifiers, model weights, or user documents are in Git.

Phase 0 does not need application behavior tests, pytest fixtures, OCR/model installs, accelerator checks, benchmarking, or repeated lint/type-check runs. Do not run the full project test suite at every phase boundary.

### Task 1 — App shell, loopback binding, safe health endpoint

**Build:** FastAPI app factory, `/api/v1/health`, localhost-only startup, safe errors, minimal static page serving.

**Do not build yet:** PII detection, file ingest, session map, LLM, or benchmark numbers.

**QA checklist:**
- [ ] Health response matches the schema and contains version/provider availability only.
- [ ] Startup binds to `127.0.0.1`; configured non-loopback host is rejected unless a future explicit security design is approved.
- [ ] An HTTP client can reach health; invalid routes return structured errors without stack traces.
- [ ] No startup request reaches the network; static page loads with networking disabled.

### Task 2 — Pure validators and deterministic detectors

**Build:** Detector protocol and Aadhaar/Verhoeff, PAN, IFSC, UPI, phone, PIN, account detectors with source/confidence/status fields.

**Do not build yet:** OCR, contextual model, redaction, restore, or UI workflows.

**QA checklist:**
- [ ] Aadhaar validator passes standard Verhoeff vectors; synthetic valid checksum cases pass and mutated check digits fail.
- [ ] Aadhaar formatted/unformatted forms normalize correctly while returned offsets still point to original text.
- [ ] PAN accepts the specified format and rejects malformed examples; reports format-only status.
- [ ] IFSC/UPI/phone/PIN/account tests cover positive, negative, boundary, and context-required cases.
- [ ] No detector logs or persists candidate values; repeated input yields identical ordered spans.
- [ ] Tests and fixtures use fake values only.

### Task 3 — Candidate merging and user review contract

**Build:** Stable merge/deduplication, overlap policy, candidate IDs stable for one analysis result, masked previews, explicit approval representation.

**Do not build yet:** Token map/session lifecycle, OCR, model-backed detection, or automatic redaction.

**QA checklist:**
- [ ] Same input yields same candidate ordering and merge result.
- [ ] Overlap cases follow priority/longest-span/tie-break rules exactly.
- [ ] Start/end offsets are valid Unicode code-point offsets and slice back to the intended source span.
- [ ] API preview is masked by default; full values require explicit reveal request.
- [ ] Ignored candidates cannot appear in approved candidate IDs.

### Task 4 — Redact/restore engine and in-memory sessions

**Build:** Collision-checked stable placeholders, repeated-span behavior, in-memory TTL session store, exact restore, unresolved-token reporting, deletion and shutdown cleanup.

**Do not build yet:** OCR, contextual model, benchmark, or polished UI.

**QA checklist:**
- [ ] Redact then restore a synthetic string reproduces the approved original spans exactly.
- [ ] Unapproved candidate remains unchanged; repeated identical approved values follow documented reuse behavior.
- [ ] Unknown/malformed tokens remain untouched and are listed; unrelated text is unchanged.
- [ ] Token-like user input cannot cause unintended restore or token-map collision.
- [ ] Delete, expiry, max-session eviction, and shutdown clear map references; no disk files are created.
- [ ] Oversized input/session requests fail before allocating unbounded memory.

### Task 5 — API workflow and security limits

**Build:** Analyze, redact, restore, delete-session endpoints and Pydantic schemas; UI-independent end-to-end path.

**Do not build yet:** OCR, LLM, device profiling, cloud connectivity, or benchmark display.

**QA checklist:**
- [ ] API integration test executes analyze → approve → redact → restore → delete.
- [ ] Session IDs are unguessable and invalid/expired IDs return a safe 404/410 response.
- [ ] Oversized bodies, invalid schema, non-loopback requests, and disallowed origins are rejected.
- [ ] Request/response errors and logs contain no full source text, identifier, or token map.
- [ ] No persistence or outbound network calls occur in the flow.

### Task 6 — Image/PDF ingestion and OCR

**Build:** Bounded upload validation, image preprocessing, RapidOCR ONNX CPU baseline, PDF text extraction and OCR fallback, extracted-text review response.

**Do not build yet:** Automatic redaction after upload, contextual LLM, unsupported formats, or arbitrary file storage.

**QA checklist:**
- [ ] Synthetic image and PDF fixtures produce expected text/category candidates within documented tolerances.
- [ ] Text PDFs use embedded text extraction; image-only pages use OCR fallback.
- [ ] Invalid MIME/signature, corrupt files, too many pages, excessive pixel dimensions, and oversized upload are rejected safely.
- [ ] Temporary data is memory-only or securely removed within request lifetime; no retained upload directory.
- [ ] CPU provider works with no accelerator installed; provider is reported accurately.

### Task 7 — Optional local contextual detector adapter

**Build:** Interface and at most one local-only implementation. Reuse a compatible local model/runtime if available; if contextual detection needs one, you are authorized to select and install a suitable model for this HP's CPU/runtime. Keep installation explicit and documented, and keep the feature optional with bounded timeout, cancellation, and degraded status. Deterministic detectors remain authoritative.

**Do not build yet:** Cloud APIs, model auto-download, mandatory model dependency, prompt-based full-document retention, or unsupported Snapdragon claims.

**QA checklist:**
- [ ] With model/runtime absent, startup and full deterministic workflow still work.
- [ ] With model present, synthetic name/address cases can add review candidates and identify their source.
- [ ] Contextual failure/timeout returns deterministic candidates and visible degraded status.
- [ ] Model receives only bounded local input; no socket/network request or content logging occurs.
- [ ] If a model is installed, its exact source, license, size, runtime requirements, and installation steps are documented; weights are not committed.

### Task 8 — Hardware capability reporting and measured benchmark

**Build:** Separate capability detection from provider selection; CPU baseline always available; optional AMD provider only if verified; placeholder adapter boundary for future QNN/GenieX. Benchmark bounded synthetic workload and report measurements with labels.

**Do not build yet:** Claims of Snapdragon support/performance, guessed numbers, automatic provider fallback hidden from UI, or broad device inventory.

**QA checklist:**
- [ ] Forced CPU mode runs on the HP regardless of detected accelerator/runtime.
- [ ] Unavailable accelerator produces explicit fallback reason; no crash or silent accelerator label.
- [ ] Benchmark output includes method, workload, repetitions, provider, runtime, device/architecture label, and elapsed time measured by monotonic clock.
- [ ] UI/README distinguish AMD development measurement from Snapdragon measurement.
- [ ] No benchmark value is hard-coded; a network-off check only claims Kavach itself made no network calls.
- [ ] Snapdragon/QNN/GenieX status remains `unverified` until run on real Snapdragon hardware with evidence.

### Task 9 — Single-page user workflow

**Build:** Text entry, upload/extracted text review, candidate reveal/edit/ignore/approve, redact, copy redacted output, paste AI response, restore, clear session, hardware/benchmark panel, clear offline/device labels.

**Do not build yet:** User accounts, chat UI, direct cloud-AI integration, browser extension, phone layout/app, or extra dashboards.

**QA checklist:**
- [ ] Complete manual round-trip works in the browser without sending content to any external service.
- [ ] Redaction requires an explicit approval action; original/redacted content are visually distinct.
- [ ] Clear/delete immediately removes session state and resets sensitive text fields.
- [ ] Keyboard-accessible labels, focus order, status/error announcements, and usable narrow desktop window verified.
- [ ] Hardware provider, model availability, and unverified Snapdragon state are understandable without developer tools.
- [ ] Browser developer network panel shows only loopback requests during the full workflow.

### Task 10 — Setup, docs, synthetic demo assets, release audit

**Build:** `setup.ps1`, concise README with architecture diagram, limitations, exact setup/run/verify commands, model provenance, troubleshooting, verified-hardware table, and 2-minute demo script. Add synthetic-only fixtures/screenshots if needed.

**Do not build yet:** Installer/MSIX, auto-updater, public hosted demo, telemetry, real-user examples, or claims unsupported by measurements.

**QA checklist:**
- [ ] Clean supported Windows environment can follow README to start app using the documented CPU baseline.
- [ ] Setup script detects x64 vs ARM64, creates local venv, installs pinned dependencies, and runs a harmless smoke check; no admin rights or silent model download.
- [ ] README hardware table says AMD HP development path only when tested and leaves Snapdragon/QDC as unverified until evidence exists.
- [ ] Architecture diagram matches actual modules and network boundary.
- [ ] Demo script completes in two minutes using synthetic data; every screenshot/recording is checked for real PII and secrets.
- [ ] Run all focused unit/integration/security checks; Ruff/type checker pass; final Git diff contains no private data, weights, uploads, or unmeasured claims.

## 5. Phased build plan for Kiro

Run each phase in order. The task numbers refer to the roadmap above and remain the detailed source of truth. Prefer the smallest clear implementation that satisfies the current task and its acceptance gate. Add a module, abstraction, dependency, configuration option, or helper only when the current requirement needs it; do not create speculative scaffolding, duplicate logic, generic frameworks, placeholder implementations, or future-phase code. Keep the planned tree as an organizational guide, not a requirement to create every listed file up front. Test proportionally: run only the checks that verify behavior changed in the current task; do not rerun the entire suite or repeat unchanged checks after every task. Run the full focused suite once at the final release audit. At every phase boundary, report changed files, commands/checks run and results, deviations, and remaining risks. Fix failed checks before moving forward. Do not wait for user approval between phases when all gates pass; stop only for a genuine blocker, a required product decision, or a failed gate that cannot be fixed within the architecture.

| Phase | Name | Tasks | Exit gate |
|---|---|---:|---|
| 0 | Repository baseline | 0 | Supported Python/environment chosen; clean install and quality tools work. |
| 1 | Safe app shell and detection foundation | 1–3 | Local-only health endpoint works; pure detectors and deterministic candidate review pass their focused checks. |
| 2 | Round-trip engine and API | 4–5 | Analyze → approve → redact → restore → delete works; session state is memory-only and security limits hold. |
| 3 | Document ingestion | 6 | Synthetic image and PDF extraction work with bounded CPU OCR and safe failure behavior. |
| 4 | Optional contextual detection | 7 | Local model adds review candidates when available; the app remains fully functional when unavailable. Skip the implementation if there is no compatible local runtime/model; preserve the adapter boundary and document the skip. |
| 5 | Hardware reporting and benchmarks | 8 | CPU path is reliable; provider and measured results are truthful and correctly labeled. |
| 6 | Complete single-page workflow | 9 | A user can finish the manual redact/copy/restore flow, inspect candidates, and clear the session. |
| 7 | Setup, documentation, and release audit | 10 | A clean supported Windows setup can run the demo; documentation and demo claims match verified evidence. |

### Copy-ready master prompt for Kiro

```text
You are the implementation engineer for Kavach. Read ARCHITECTURE.md in full before changing files. Treat its product contract, repository structure, API contract, invariants, task boundaries, and QA checklists as binding requirements. If the repository differs from the document, inspect first and report the discrepancy; do not overwrite or discard existing work.

Build Kavach phase by phase, in the exact order in Section 5 of ARCHITECTURE.md. Use the detailed task checklists in Section 4 as each phase's acceptance gates. Make small, reviewable changes. After each phase, run its focused checks, repair failures, then report the files changed, commands and results, and any skipped items with reasons. Continue to the next phase automatically when the gate passes. Stop only for a real blocker or a product decision the architecture does not answer.

Hard constraints:
- Optimize for good code, not more code. Before adding a file or abstraction, confirm it is needed for the current phase. Prefer a few cohesive modules, direct control flow, and standard-library features where appropriate. Do not make generic frameworks or speculative extension points; keep only the specific adapter boundaries required by the architecture.
- Do not implement future-phase features early. Do not scaffold empty files/classes/functions merely because they appear in the proposed directory tree. Create files when the phase needs them.
- Keep tests proportional to the current behavior: focused tests for the acceptance criteria, no redundant test layers or fixtures. Never use generated boilerplate to inflate coverage.
- Do not run broad or repeated testing without a reason. Phase 0 is limited to environment/dependency smoke checks; add behavior tests only when that phase adds behavior, and run the complete applicable suite during the final release audit.
- Keep the first supported runtime path on this HP PC's Windows x86-64 CPU. AMD NPU work is optional and must not break CPU operation. Qualcomm/Snapdragon, QNN, and GenieX are unverified until actually run on Snapdragon hardware; never claim otherwise.
- Keep all user text, documents, detected values, and token mappings local and in memory. No outbound content requests, telemetry, persistence, or sensitive logs. Never add real PII to source, fixtures, screenshots, or demo material.
- Do not add cloud integrations, user accounts, phone apps, multi-device features, browser extensions, auto-updaters, or unrelated UI.
- A local model may be installed for Task 7 if contextual detection needs it. Do not download it silently or commit its weights; report its source, license, size, runtime requirements, and install steps. The app must remain usable without the model or an accelerator.
- Do not invent benchmark results. Measure on the actual current device, label the provider/device accurately, and distinguish AMD development results from Snapdragon results.
- Preserve the specified detector confidence limits, explicit review/approval before redaction, exact-token restore behavior, localhost-only default, file and memory limits, and cleanup rules.
- Keep dependencies compatible with the actual Windows/Python architecture and pin them. If a dependency/runtime cannot be installed or verified, implement the documented fallback and state the limitation rather than claiming success.
- Do not expand a task beyond its stated “Build” scope. Respect each task's “Do not build yet” boundaries.

Begin with Phase 0 only. Inspect the existing repository, determine the actual Python version and machine architecture, and implement Task 0. Keep Phase 0 to a minimal environment/dependency smoke check; do not create application tests or install later-phase OCR/model/accelerator dependencies. Do not begin Phase 1 until Task 0's gate passes. In Phase 1, implement only the app shell and detector/merge behavior needed for Tasks 1–3; do not create empty files for sessions, OCR, contextual models, hardware, or UI workflow. Test only behavior changed in the current phase; reserve the complete applicable test suite for the final release audit. Then continue sequentially through all phases, honoring optional skips and stopping at genuine blockers. At completion, provide a concise phase-by-phase status table, verification evidence, actual hardware/provider tested, unverified items, and exact run instructions. Do not claim a check passed unless you ran it and observed the result.
```

### Phase-specific continuation prompts

Use these only if Kiro is paused or you want to control phase advancement manually. Paste one prompt at a time after reviewing the previous phase report.

**Phase 0:** `Read ARCHITECTURE.md. Inspect the existing repository and implement only Task 0 (repository and dependency baseline). Identify the actual Python version and architecture before pinning the minimal Phase 0 dependencies. Do only the Task 0 environment/dependency smoke checks. Do not write application tests, install OCR/model/accelerator dependencies, or start Task 1.`

**Phase 1:** `Implement Tasks 1–3 only, following ARCHITECTURE.md: safe app shell, deterministic India-aware detectors, and candidate merging/review contract. Keep this lean: create only files needed for these behaviors, avoid speculative abstractions and duplicate helpers, and do not scaffold later-phase modules. Run only focused checks for these tasks, fix failures, and report evidence. Do not implement sessions, redaction, restore, OCR, contextual models, benchmarks, or UI workflow.`

**Phase 2:** `Implement Tasks 4–5 only: in-memory round-trip engine, session lifecycle, API flow, and security limits. Run their QA checklists and report evidence. Do not implement OCR, contextual models, hardware benchmarking, or polished UI.`

**Phase 3:** `Implement Task 6 only: bounded image/PDF ingestion and RapidOCR CPU baseline. Keep extracted text in the review flow; do not redact automatically. Run the Task 6 QA checklist and report evidence.`

**Phase 4:** `Implement Task 7 only. First check whether a compatible local model/runtime is already available. If contextual detection needs a model, you are authorized to select and install one suitable for this HP's CPU/runtime; choose at most one and document its exact source, license, size, runtime requirements, and install steps. Keep the model optional, keep the app functional without it, and never add a cloud API. Run only Task 7's focused checks.`

**Phase 5:** `Implement Task 8 only: capability reporting, explicit provider selection/fallback, and measured local benchmark. Keep CPU as the guaranteed path. Do not claim Snapdragon support or add guessed values. Run the Task 8 QA checklist and report actual device/provider evidence.`

**Phase 6:** `Implement Task 9 only: the single-page end-to-end manual workflow. Use existing API contracts and design. Run the Task 9 QA checklist, including checking that browser requests stay on loopback.`

**Phase 7:** `Implement Task 10 only: setup.ps1, README, synthetic demo material, and release audit. Run the Task 10 QA checklist. Report only hardware and benchmark claims supported by evidence from this machine; leave Snapdragon/QDC unverified unless actually tested there.`

## 6. Definition of done

The first deliverable is complete when a user can run Kavach locally on the HP CPU path, upload a supported synthetic document or paste text, inspect and approve detections, copy redacted text to an external AI manually, paste the response back, restore only known placeholders, clear the session, and view truthful device/provider status. All content stays local to Kavach, and every claim in documentation is supported by a reproducible check or clearly marked unverified.

A Snapdragon-optimized claim is a separate acceptance gate: execute the documented smoke path on actual Snapdragon hardware, verify the selected Qualcomm runtime/provider rather than inferring from device name, record the environment and measured workload, and update only the claims supported by that evidence.
