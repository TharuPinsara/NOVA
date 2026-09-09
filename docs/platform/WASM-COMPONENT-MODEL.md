# NOVA — WebAssembly Component Model & WIT Integration

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


**Status:** Production Design Reference  
**Cross-References:** [INTEROPERABILITY.md](INTEROPERABILITY.md), [ECOSYSTEM-BRIDGES.md](ECOSYSTEM-BRIDGES.md), [APPLICATION-MODEL.md](../full-stack/APPLICATION-MODEL.md)

---

## 1. WebAssembly Interface Types (WIT) Integration

NOVA natively supports the W3C WebAssembly Component Model. Every NOVA package can export and import standard `.wit` interface definitions:

```wit
// WIT Interface: search.wit
package nova:search;

interface engine {
    record search-request {
        query: string,
        limit: u32,
    }

    record search-result {
        id: string,
        score: float32,
    }

    query-index: func(req: search-request) -> list<search-result>;
}
```

---

## 2. Compiling NOVA to WASM Components

> **Current implementation status:** NOVA 0.2 does not emit WASM/WASI
> components. `nova build --target wasm` and `--target wasi` fail closed;
> they must never fall back to an interpreter-backed executable, because that
> executable would have the authority of its host process.

### 2.1 WASI Preview 2 authority boundary

When the component backend is implemented, every guest instantiation MUST
start with **zero preopened directory descriptors** and no filesystem
authority. A host may add a preopen only for an explicit, unforgeable
filesystem capability token declared by the package's `nova.toml`. The host
must not infer preopens from the current directory, the source directory,
environment variables, or the parent process.

The same rule applies to autonomous AI-agent invocations: an agent starts
with an empty capability set and receives only tokens explicitly delegated by
its caller. Agent code cannot acquire filesystem authority merely by asking
the runtime to invoke a WASI component.

This is a host-instantiation requirement, not a property provided by WASM
linear-memory isolation alone. The eventual Preview 2 host must therefore
construct its WASI context from the manifest's declared tokens rather than
using convenience APIs that inherit ambient preopens.

The NOVA compiler produces standard WASM components directly:

```bash
nova build src/engine.nova --target wasm32-wasi-component -o search_engine.wasm
```

```nova
// Implementing the WIT interface in NOVA:
export search.engine {
    fn query_index(req: SearchRequest) -> List[SearchResult] {
        // Pure implementation compiled to sandboxed WebAssembly component
        execute_search(req.query, req.limit)
    }
}
```

---

## 3. Polyglot Component Composition

Because NOVA components adhere to the canonical WASM Component Model ABI, they compose seamlessly with components written in other languages:

```
+-------------------------------------------------------------+
|                  Wasmtime / Edge Runtime Sandbox            |
|                                                             |
|  +---------------------+        +------------------------+  |
|  | NOVA Business Logic | <----> | Rust Cryptography Core |  |
|  +---------------------+        +------------------------+  |
|            │                                                |
|            ▼                                                |
|  +---------------------+                                    |
|  | Python ML Predictor |                                    |
|  +---------------------+                                    |
+-------------------------------------------------------------+
```

* Zero native C FFI security vulnerabilities.
* Memory isolation enforced by WebAssembly linear memory sandboxes.
* Standardized binary serialization over the Canonical ABI.
