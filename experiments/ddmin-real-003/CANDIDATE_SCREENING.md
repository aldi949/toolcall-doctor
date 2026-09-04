# Candidate screening (Bug #003)

Screening is **not** DDMin. No payload reduction. No invariant tuning after HTTP.

## Environment (this host)

- Ollama 0.4.6 at `127.0.0.1:11434`
- Model: `llama3.2:3b` only
- 4 GB VRAM: 7B/14B/32B/70B not treated as executable
- jsonschema 4.26.0

## Pool

Reuse the Bug #002B live-screen order (ollama issues ascending). Do not prefer
ease of minimization. Prefer a failure whose **meaningful constraint can
degenerate** and that already reproduces stably.

### Already live-screened on this host (Bug #002B `SCREEN_LOG.json`)

| issue | failure | N | result | Bug #003 decision |
|---|---|---|---|---|
| ollama#11805 | extra nested arguments | 0/3 | NON_MANIFESTING | reject |
| ollama#13750 | tools + response_format | 0/3 | NON_MANIFESTING | reject |
| ollama#14181 | tool markup in content | 2/10 | FLAKY | reject — cannot support identity preservation |
| ollama#14967 | tool_choice name mismatch | 0/3 | NON_MANIFESTING | reject |
| ollama#16932 | param `name` drops call | 0/3 | NON_MANIFESTING | reject |
| ollama#17597 | tool param `enum` not enforced | 3/3 | MANIFESTED_STABLE | **primary candidate** |

### Considered, not selected

**Diagnostic `experiments/bug-003/` nested `press_button` (ollama#13472).**  
Already 3/3 HTTP 200 schema-invalid nested args on this host (`/api/chat`).  
Rejected for *this* experiment: (1) that tree is a frozen diagnostic study and must not be reused as if it were DDMin #003; (2) the research question is specifically whether a gate can block the **#002B `enum=[]` degeneration**; (3) mixing `/api/chat` vs `/v1` would add a confound.

No new GitHub crawl was required: the executable HTTP-200 behavioral pool on this machine is already known, and only #17597 was stable.

## Fresh pre-freeze reproduction (this tree)

Executed 2026-09-03T18:55:56Z into `original/raw` and `control/raw`.

- Original: **3/3** HTTP 200, `{"account":"ACC-999-XYZ"}`, behavioral FAIL, semantic gate OK
- Control: **3/3** HTTP 200, `{"account":"ONLY-VALID-ACCOUNT"}`, behavioral PASS (schema-valid)
- Unanimous failing value frozen: `ACC-999-XYZ`
- Atoms: 160. Request-side search freedom: 113/160 (70.63%) single-atom drops still satisfy request-only semantic invariants.

**Selected failure:** ollama#17597 RELATED enum-not-enforced on `llama3.2:3b`.
