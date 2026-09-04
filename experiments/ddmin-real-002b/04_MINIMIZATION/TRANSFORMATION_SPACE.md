# Frozen transformation space (before any minimization HTTP)

This file is hashed into `03_FREEZE/FREEZE_MANIFEST.json`. It must not change after that hash.

## Representation

The original JSON request is decomposed into an ordered list of **atoms**.
Delta debugging runs over this list. A candidate configuration is a subset `S`
of atom IDs. The HTTP payload is `reconstruct(original, S)`.

No key is semantically protected. `model`, `messages`, and `tools` are ordinary
top-level key atoms and may be absent.

## Atom kinds

Atoms are produced by a generic walk of the original JSON value:

1. **key** — for every object key, including nested keys. ID:
   `key:<json-pointer-ish path>/<keyname>`
   Example: `key:/model`, `key:/tools/0/function/name`.
2. **idx** — for every array element. ID: `idx:<path>/<index>`
   Example: `idx:/messages/0`, `idx:/tools/0/function/parameters/properties/query/type/1`.
3. **char** — for every character of every JSON string value. ID:
   `char:<path-to-string>/<char-index>`
   Example: `char:/messages/0/content/0` is the first character of `"Hello"`.

Numbers, booleans, and null have no sub-atoms. Keeping the parent key keeps
the original primitive value.

## Reconstruction

`reconstruct(original, S)` walks the original value:

- Object: copy a key only if its **key** atom is in `S`. Recurse into the value.
  If no keys remain, the object is `{}`.
- Array: copy an element only if its **idx** atom is in `S`. Recurse into the
  element. If no elements remain, the array is `[]`.
- String: emit the concatenation of characters whose **char** atoms are in `S`.
  If none remain, the string is `""`.
- Primitive: emit the original value.

### Ancestor effectiveness

An atom is **effective** in `S` only if every ancestor structural atom
(all **key** / **idx** atoms on the path from the document root to that atom)
is also in `S`. Character atoms require their string's parent key or idx.

Reconstruction already implements this (a missing parent omits children).

After every **accepted** DDMin reduction, the current set `C` is replaced by
`effective(C)` so inert (ancestor-missing) atoms are not retained. This is a
deterministic function of `C` and the frozen atom table. It is not a manual
choice of which keys matter.

## What is NOT in this space

These are **not** transformations (they would be extra mutations, not subset
selection over the original):

- Scalarizing a JSON array into a non-array JSON value (for example
  `["null"]` → `"null"`).
- Renaming keys.
- Changing number/bool values.
- Adding keys that were not in the original.
- Reordering object keys as a searched transformation (JSON object order is
  not treated as an atom).
- Reading any previously minimized payload.

Empty arrays and empty objects **are** in the space: they arise when a parent
key/idx is kept and all child idx/key atoms are removed.

String shortening **is** in the space via **char** atoms.

## DDMin procedure (frozen)

Let `C` be the current list of atom IDs (order = extraction order, then the
relative order of whatever remains).

1. Seed: test `S = all atoms` (the original request). Must FAIL the target
   identity or the run stops.
2. Set granularity `n = 2`.
3. Partition `C` into `n` contiguous blocks `Δ1 .. Δn` as evenly as possible.
4. **Remove-subset tests:** for each `Δi`, test remaining `C \ Δi`.
   If the target identity is preserved, accept `C := effective(C \ Δi)`,
   set `n = max(n - 1, 2)`, go to step 3.
5. **Complement / keep-subset tests:** for each `Δi`, test remaining `Δi`.
   If the target identity is preserved, accept `C := effective(Δi)`,
   set `n = max(n - 1, 2)`, go to step 3.
6. If no reduction in this round: if `n >= |C|`, stop; else
   `n = min(2n, |C|)` and go to step 3.

A test is accepted as a new current configuration only if
`oracle == FAIL` and `failure_identity == HTTP_200_TOOL_ARGS_ENUM_VIOLATION`
on **all N independent POSTs** of that candidate (see frozen repetition policy).

Every test is one new candidate ID, N HTTP POSTs, one ledger line. Candidate
directories are never reused. Equivalent payloads may still be posted if the
algorithm emits them.

Partitioning is by the current ordered list, not by JSON semantics.

## 1-minimality (independent verifier)

After DDMin stops, for each remaining atom `a` in the final `C`, test
`effective(C \ {a})` once (same N-repetition oracle). If any such test still
preserves the target identity, the result is **not** 1-minimal in this space.

Overlapping hierarchy is resolved only by the reconstruction/effectiveness
rules above. The verifier does not invent a second atom encoding.
