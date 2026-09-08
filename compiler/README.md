# NOVA toolchain (`nova`)

The developer-facing CLI for NOVA. It is a thin driver around two things:

1. **`verifier/refspec/`** — the reference frontend and interpreter. This
   is the authoritative implementation of the language: lexer, parser,
   Hindley–Milner type inference, row-typed effect checking, capability
   reachability analysis, and a tree-walking reference evaluator. Every
   semantic rule lives here and is exercised by `tests/conformance/`.

2. **`compiler/nova_compiler/`** — the CLI (`nova <command>`), plus a
   **best-effort** native C backend for the first-order subset of the
   language.

## Pipeline

```
Source (.nova)
   │  verifier/refspec/  (authoritative)
   ▼
Lexer → Parser → AST → name/module resolution → type & effect inference
   → capability reachability
   │
   ├─► nova check   — stop here, report diagnostics
   ├─► nova run     — hand the checked AST to the reference interpreter
   └─► nova build   — attempt native C codegen, else emit an
                       interpreter-backed runner
```

`HIR`/`MIR` (`hir.py`, `mir.py`) exist as **informational lowerings**
surfaced by `--emit-hir` / `--emit-mir`. They are not on the execution
path and are not a full IR yet.

## Import discipline in `cli.py` / `driver.py`

Every subcommand's own module is imported **inside its branch**, not at
the top of `cli.py` — `nova check` has no reason to pay for `pkg.py`'s
`tarfile`/`hashlib`, or `lsp_server`, `docgen`, `fmt`, `lint` on every
invocation. Likewise `driver.py` only imports `hir`/`mir`/`codegen_c`
inside `build_file()`, past its cache-hit fast path, since `check_file()`
and `run_file()` never touch native codegen. Keep new subcommands and new
`NovaCompiler` methods lazy in the same way — this is what took `nova
check`'s median invocation from ~121ms to ~86ms (see `docs/known-issues.md`
C5). It is pure process-startup overhead, not compiled-program speed.

## The native C backend

`codegen_c.py` lowers a **supported subset** to C99 and links it with
`clang`:

| Supported | Not yet lowered (falls back to the interpreter) |
| :--- | :--- |
| top-level `fn`s | enums, `match` |
| `Int` `Bool` `String` `Unit` | closures, `for` |
| `struct` types | generics, traits / `impl` |
| `Runtime`, `Clock` | tuples, `List`, imports beyond the prelude |
| arithmetic / comparison / `if` / `while` / `let mut` | |

When a program uses anything in the right-hand column, `nova build`
prints `Backend: interpreter-backed runner` and emits a small runnable
artifact that executes the program through the reference interpreter. The
program still runs and still returns the right value — it is just not a
standalone machine binary.

This is deliberate: the backend never emits C it cannot compile, so
`nova build` never produces a broken binary.

## Commands

```
nova new <name>       scaffold a project
nova check <file>     type- and effect-check
nova run <file>       check and execute (reference interpreter)
nova dev <file>       alias for run, for the inner loop
nova build <file>     produce an executable artifact (native or runner)
nova test [pattern]   run the conformance and prototype suites
nova fmt / lint       format / lint .nova sources
nova doc <path>       generate API docs
nova add / remove / update / publish / deploy
                      package-manifest helpers (no registry yet — see
                      docs/known-issues.md P3)
nova lsp              language server over stdio
nova bench <file>     wall-clock build/run timings for one file
```
