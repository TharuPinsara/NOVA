# NOVA — Authoritative Implementation Map & Consolidation Strategy

<!-- STATUS-BANNER -->
> **Status note (added in the 0.2 honesty pass).** This document is part
> of NOVA's *design record*. It was written in the aspirational voice of
> a finished 1.0 platform. **NOVA is a 0.2 research preview.** What is
> actually built and tested is a frontend type/effect/capability checker,
> a reference interpreter, a first-order native C backend, and the
> `regionlab` memory-model prototype. Everything here about a distributed
> runtime, a WASM UI layer, AI-agent governance, a package registry,
> self-hosting, or cross-language performance is **design, not
> implementation**. See [`README.md`](../../README.md),
> [`ROADMAP.md`](../../ROADMAP.md) and
> [`docs/known-issues.md`](../known-issues.md) for the real state.


**Status:** Ratified source of truth (2026-09-10)
**Cross-References:** [LANGUAGE-CONSTITUTION.md](LANGUAGE-CONSTITUTION.md), [COMPILER-AUDIT-REPORT.md](COMPILER-AUDIT-REPORT.md), [ARCHITECTURE.md](../runtime/ARCHITECTURE.md)

---

## 1. Subsystem Authority Classification

This document formally establishes which codebase is authoritative for every major subsystem to prevent contributor confusion and eliminate duplicate parallel implementations.

This map is normative for repository changes. When code, a README, or an
older design document disagrees with this table, contributors must route the
change to the authoritative path below and correct the stale documentation in
the same PR. A secondary path may contain experiments or migration sketches,
but it must not grow a competing implementation of an owned subsystem.

| Subsystem | Authoritative Codebase | Secondary / Migration Status | Purpose & Role |
| :--- | :--- | :--- | :--- |
| **CLI & Driver** | [`compiler/nova_compiler/cli.py`](../../compiler/nova_compiler/cli.py) | Authoritative | Single entrypoint for `nova new`, `dev`, `check`, `build`, `run`, `test`, `fmt`, `lint`, `doc`, `add`, `remove`, `update`, `publish`, `deploy`, `lsp`, `bench`. |
| **Frontend & Verifier** | [`verifier/refspec/`](../../verifier/refspec/) | **Authoritative — this is the language.** | Reference Hindley-Milner type inference, row-typed effect lattice, transitive capability reachability, and the tree-walking reference interpreter (`eval.py`). Every semantic rule lives here. |
| **Intermediate Representations** | [`compiler/nova_compiler/hir.py`](../../compiler/nova_compiler/hir.py) & [`mir.py`](../../compiler/nova_compiler/mir.py) | **Informational scaffolding, not a real IR.** | Surfaced by `--emit-hir` / `--emit-mir`. Not on the execution path. Pattern-tree desugaring, monomorphization and drop elaboration are Milestone 3, not done. See [known-issues](../known-issues.md) C2. |
| **Backend Codegen** | [`compiler/nova_compiler/codegen_c.py`](../../compiler/nova_compiler/codegen_c.py) | **First-order subset only.** | Lowers top-level `fn`s over `Int` / `Bool` / `String` / `Unit` / `struct` with `Runtime` / `Clock` to a native binary via `clang`. Enums, `match`, closures, generics, traits, `List`, `for`, tuples, WASM: **not lowered** — `nova build` falls back to an interpreter-backed runner. See [known-issues](../known-issues.md) C1. |
| **Memory Model** | [`regionlab/`](../../regionlab/) | Prototype, **not integrated** | Standalone operational semantics & 14-test harness for Region XOR (Shared Read XOR Exclusive Write). Integration into the main checker is Milestone 1. |
| **Self-Hosted Sources** | [`src/`](../../src/) | Deprecated sketch; not an implementation | `src/compiler/*.nova` names a future bootstrap shape but does not implement a compiler. New compiler behavior belongs in `verifier/refspec/` or `compiler/nova_compiler/` according to the table. |
| **Standard Library** | [`std/`](../../std/) | Authoritative prelude, minimal | `prelude.nova` (capabilities: `Runtime`, `Clock`, `Filesystem`, `Network`), `option.nova`, `result.nova`, `list.nova`. No string ops ([known-issues](../known-issues.md) C3). |
| **Language Server** | [`compiler/nova_compiler/lsp_server.py`](../../compiler/nova_compiler/lsp_server.py) | Authoritative, minimal | ~170 lines over stdio. [`lsp/server.py`](../../lsp/server.py) is a deprecated compatibility launcher only; protocol behavior must not be added there. |

---

## 2. Consolidation & Deprecation Action Items

1. **LSP Consolidation:** All IDE extensions must invoke `nova lsp` which routes to [`compiler/nova_compiler/lsp_server.py`](../../compiler/nova_compiler/lsp_server.py).
2. **Self-Hosting Bootstrap Chain:** [`src/compiler/`](../../src/compiler/) mirrors the AST and type checking logic in pure NOVA, verified against [`verifier/refspec/`](../../verifier/refspec/) test vectors.
3. **Memory Model Integration:** The RegionLab checker rules (`regionlab/checker.py`) serve as the formal specification for lowering lifetime scopes into MIR drop flags.

## 3. Contributor routing rule

Every incoming PR must identify its owning row in section 1 before
implementation:

| Change | Route the implementation to | Required companion validation |
| :--- | :--- | :--- |
| Language syntax, typing, effects, capabilities, modules, interpreter semantics | [`verifier/refspec/`](../../verifier/refspec/) | Add or update a conformance test under [`tests/conformance/`](../../tests/conformance/) |
| CLI, diagnostics, formatting, linting, package helpers, LSP | [`compiler/nova_compiler/`](../../compiler/nova_compiler/) | Add the narrow toolchain/LSP test, then run `tools/check-all.sh` |
| HIR/MIR lowering | [`compiler/nova_compiler/hir.py`](../../compiler/nova_compiler/hir.py) / [`mir.py`](../../compiler/nova_compiler/mir.py) | Add a lowering regression; do not create another frontend or checker |
| Native C backend | [`compiler/nova_compiler/codegen_c.py`](../../compiler/nova_compiler/codegen_c.py) | Add a backend test and preserve interpreter fallback for unsupported constructs |
| Region XOR prototype | [`regionlab/`](../../regionlab/) | Add a RegionLab test; do not copy its checker into `verifier/refspec/` |
| Self-hosting experiments | [`src/`](../../src/) only when explicitly scoped as a bootstrap experiment | Mark the work as non-authoritative and keep behavior aligned with conformance |

PR descriptions should name the authority row, the test added, and any
documentation that was corrected. A PR that adds a second implementation
without an explicit migration plan is out of scope.
