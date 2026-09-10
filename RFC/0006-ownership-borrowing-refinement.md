# RFC 0006 - Ownership and Borrowing Syntax Refinement

- **Status:** Draft
- **Created:** 2026-09-10
- **Depends on:** [RFC 0001](0001-core-capability-effects.md), [RFC 0002](0002-structs-tuples-enums-pattern-matching.md), [RFC 0005](0005-local-mutability-and-loops.md), [OWNERSHIP-MODEL.md](../docs/language/OWNERSHIP-MODEL.md)
- **Issue:** #34

## 1. Summary

This RFC introduces explicit value-level shared and exclusive references:
`&T` for read-only borrowing and `&mut T` for writable borrowing. The
references refine the region-level mechanism already specified by
[OWNERSHIP-MODEL.md](../docs/language/OWNERSHIP-MODEL.md): shared references
may coexist, while an exclusive reference is unique and linear. Region
identity and borrow duration remain compiler-inferred; NOVA source does not
introduce named lifetime parameters. The proposal makes borrowing visible in
function signatures and expressions without adopting Rust's field-level
borrow splitting or its lifetime annotation language.

The issue description mentions `RFC/0002-memory-and-borrowing.md`. That file
does not exist in this repository; RFC 0002 is the data-types and pattern-
matching RFC. This proposal therefore treats OWNERSHIP-MODEL.md and the
existing RFC 0002 as the normative local sources.

## 2. Problem

The current ownership design describes `&Region` and `&mut Region`, but it
does not specify how a function borrows an individual region-owned value. A
function must either receive an owned `InRegion[T]` value, which risks moving
the value when only inspection was intended, or rely on an underspecified
capability convention.

For example, a read-only helper should say that it cannot mutate its input:

```nova
fn length(xs: &List[Int]) -> Int {
    // read xs
    0
}
```

A mutating helper should say that it needs the unique write permission:

```nova
fn append_one(xs: &mut List[Int]) -> Unit {
    // update xs
}
```

Without a reference type, the signature does not express that distinction.
Without a checked borrow expression, the caller cannot see where the access
begins or ends. That gap makes the Region XOR claim precise for capabilities
but incomplete for ordinary function APIs.

The design must preserve these properties:

1. Multiple concurrent readers of one region are valid.
2. A writer excludes every reader and every other writer in that region.
3. A reference cannot outlive its source value or region.
4. Moving an exclusive reference transfers the only write authority.
5. No source-level lifetime annotations are required.

## 3. Prior art

### Rust

Rust writes shared and exclusive references as `&T` and `&mut T`, checks
aliasing per value, and exposes lifetime parameters when inference cannot
prove the required relationship. This proposal adopts the familiar syntax and
the shared/exclusive distinction, but checks conflicts at NOVA's region
boundary. It consequently remains simpler and rejects some programs Rust can
accept, such as simultaneous mutable borrows of disjoint fields in one region.

### Koka

Koka infers effect rows and uses explicit effect-polymorphic function types.
It makes computational effects visible, but does not provide NOVA's linear
exclusive region capability. RFC 0001 remains responsible for effect and
capability rows; this RFC only refines memory access values.

### Pony

Pony separates `iso`, `trn`, `ref`, `val`, and `tag` capabilities and derives
concurrency guarantees from reference permissions. Its permissions are a
useful precedent for making aliasing visible, but its reference capability
lattice is larger than NOVA needs. NOVA keeps two source-level permissions and
uses regions as the unit of exclusion.

### Swift

Swift uses value semantics by default and provides `inout` for exclusive
access during a call. `inout` demonstrates that a call-scoped exclusive
borrow can be ergonomic, but it does not provide NOVA's first-class linear
capability or region-wide shared-read rule. This RFC allows `&mut T` to move
between calls, subject to linearity.

### Haskell

Haskell's immutable values make shared reads easy, while `ST` uses a phantom
state parameter to prevent mutable state from escaping its computation. NOVA
gets the same non-escape guarantee from lexical regions and inferred region
constraints, without exposing a state-token parameter in ordinary source.

### TypeScript

TypeScript's structural types can describe readonly properties, but its
runtime aliasing and mutation rules are not a data-race or lifetime system.
`readonly` is therefore useful API documentation but is not a substitute for
`&T` and `&mut T` in a language promising Region XOR.

## 4. Design

### 4.1 Surface syntax

The following type forms and expressions are added:

```nova
&T       // shared, read-only reference to a T
&mut T   // exclusive, writable reference to a T
&value   // create a shared borrow of value
&mut value // create an exclusive borrow of value
```

Whitespace between `&mut` and `T` is optional only where the lexer already
recognizes `mut` as a keyword; the canonical spelling is `&mut T`.

References are ordinary typed values, but they are not owning values. The
source value remains owned by its original binding while a borrow is live.
The region capability forms retain their existing meaning:

```nova
&Region       // shared access to all values in a region
&mut Region   // linear exclusive access to a region
```

`&T` and `&mut T` are value-level projections of those permissions. If `T` is
region-owned, its reference carries the region identity internally. If `T` is
an immediate value such as `Int`, borrowing is permitted for uniformity but
has no required heap allocation or runtime indirection in an optimized
backend.

### 4.2 Function signatures

References may appear in parameters, results, local bindings, tuple fields,
and generic substitutions, subject to the escape rules in section 4.6:

```nova
fn read_first(xs: &List[Int]) -> Int {
    // shared reads are allowed
    0
}

fn replace_first(xs: &mut List[Int], value: Int) -> Unit {
    // writes require the exclusive reference
}
```

A function receiving `&T` cannot write through it. A function receiving
`&mut T` may read and write through it, but the capability is linear: passing
it onward moves it and leaves the caller without that reference until it is
returned or the borrow ends.

### 4.3 Static access rule: Region XOR

For every live region `r`, the checker tracks one of these states:

```text
Idle
Shared(n), where n > 0
Exclusive(owner)
```

The transitions are:

| Operation | Required state | New state |
| --- | --- | --- |
| `&value` where `value` is in `r` | `Idle` or `Shared(n)` | `Shared(n + 1)` |
| `&mut value` where `value` is in `r` | `Idle` | `Exclusive(borrow)` |
| end of a shared borrow | `Shared(n)` | `Shared(n - 1)` |
| end of an exclusive borrow | `Exclusive(borrow)` | `Idle` |
| shared-to-shared copy | `Shared(n)` | `Shared(n + 1)` |
| move of an exclusive reference | `Exclusive(owner)` | `Exclusive(new-owner)` |

An exclusive borrow is rejected if any shared or exclusive borrow of the
same region is live. A shared borrow is rejected while an exclusive borrow of
the same region is live. The checker may use a more precise internal identity
for diagnostics, but the safety boundary is the region, not an individual
field.

The resulting invariant is:

> For every region, `shared_count > 0` XOR `exclusive_live`.

The invariant applies during task migration as well as ordinary calls. A
suspended frame carrying `&mut T` must transfer its exclusive lease and frame
ownership under one scheduler synchronization gate, as specified in
[MEMORY-MODEL.md](../docs/language/MEMORY-MODEL.md#81-concurrent-frame-migration-reference-protocol).

### 4.4 Borrow expressions and scope

A borrow expression creates a reference whose minimum valid scope is the
lexical block containing the expression. The checker may shorten that scope
to the last use, but never extends it beyond the source value or region.

```nova
region r {
    let value = alloc(r, 7);
    {
        let view: &InRegion[Int] = &value;
        read(view);
    }
    // `view` is gone here; a mutable borrow may begin now.
    let edit: &mut InRegion[Int] = &mut value;
    write(edit, 8);
}
```

The source binding cannot be moved, closed, or mutably borrowed in a way that
would invalidate a live shared reference. An exclusive reference prevents any
other borrow of its region until it ends or is explicitly returned.

The first implementation may use lexical end-of-block release only. Last-use
shortening is an optimization and must not change accepted or rejected
programs.

### 4.5 Reborrowing

The initial design permits a shared reborrow of an exclusive reference only
for a nested lexical scope:

```nova
fn inspect_then_edit(value: &mut T) -> T {
    {
        let view: &T = value;
        inspect(view);
    }
    edit(value);
}
```

During the nested scope, the exclusive reference is suspended and cannot be
used. After the shared reborrow ends, the exclusive reference becomes usable
again. The checker rejects use of the exclusive reference while `view` is
live.

Exclusive reborrowing is a move, not a copy:

```nova
let inner: &mut T = value;
// `value` is unavailable until `inner` is returned or ends.
```

Returning `inner` to the caller is represented by ordinary return flow; no
special lifetime syntax is added.

### 4.6 Region and escape constraints

The compiler assigns each borrow an internal region variable and generates
constraints from the source value, uses, calls, and return path. These
variables are implementation details and never appear in NOVA syntax.

A reference is valid only when all of the following hold:

1. Its source value is still live.
2. Its source region is still open.
3. Its inferred borrow interval is contained by the source interval.
4. A returned reference is backed by a region live in the caller.
5. A stored reference is backed by a region that outlives the containing
   object for the object's entire valid interval.

A reference into a region opened inside the current function cannot be
returned, stored in an escaping closure, sent to a longer-lived task, or
placed in a value that outlives that region. This is the reference form of the
existing `InRegion[T]` non-escape rule.

A function may return a reference borrowed from an input when inference can
prove the input's region outlives the result. For example, the following is
valid in principle:

```nova
fn identity[T](value: &T) -> &T { value }
```

The compiler infers that the result is tied to the input borrow. No caller
may use the result after the input's source region ends.

### 4.7 Copy, move, and concurrency behavior

- `&T` is shared and copyable. Each copy increments the shared borrow count
  for the referenced region.
- `&mut T` is linear and movable. A move invalidates the source binding.
- Neither reference form owns the referent or closes its region.
- `&T` may cross a task boundary when its region remains live and the task
  receives read-only access.
- `&mut T` may cross a task boundary only as a linear move. The donor task
  loses access before the recipient can use the reference.
- A work-stealing scheduler must not copy an exclusive reference while
  migrating a frame. The handoff is a capability transfer, not a second
  borrow.

These rules derive Send/Share behavior from the same distinction as the
existing ownership model; no separate marker-trait system is introduced.

### 4.8 Diagnostics

The implementation should use stable diagnostic codes for the core errors:

```text
E1101 cannot create shared borrow: region `r` has an active exclusive borrow
E1102 cannot create exclusive borrow: region `r` has live shared borrows
E1103 cannot use moved exclusive reference `view`
E1104 reference to region `r` escapes its owning scope
E1105 cannot write through shared reference `view`
E1106 cannot use exclusive reference `edit` while shared reborrow is live
```

The exact wording may evolve, but diagnostics must identify the conflicting
binding and region where available.

## 5. Examples

### 5.1 Accepted: concurrent reads

```nova
region r {
    let value = alloc(r, 10);
    let a: &InRegion[Int] = &value;
    let b: &InRegion[Int] = a;
    read(a);
    read(b);
}
```

Both references are read-only and share one region safely.

### 5.2 Accepted: exclusive write after reads end

```nova
region r {
    let value = alloc(r, 10);
    {
        let view: &InRegion[Int] = &value;
        read(view);
    }
    let edit: &mut InRegion[Int] = &mut value;
    write(edit, 11);
}
```

### 5.3 Rejected: write through a shared reference

```nova
fn bad(value: &InRegion[Int]) -> Int {
    write(value, 1)
    0
}
```

```text
error[E1105]: cannot write through shared reference `value`
```

### 5.4 Rejected: shared and exclusive overlap

```nova
region r {
    let value = alloc(r, 10);
    let view: &InRegion[Int] = &value;
    let edit: &mut InRegion[Int] = &mut value;
}
```

```text
error[E1102]: cannot create exclusive borrow: region `r` has live shared borrows
```

### 5.5 Rejected: local-region reference escapes

```nova
fn bad() -> &InRegion[Int] {
    region local {
        let value = alloc(local, 10);
        &value
    }
}
```

```text
error[E1104]: reference to region `local` escapes its owning scope
```

### 5.6 Rejected: exclusive reference copied by a closure

```nova
fn bad(value: &mut InRegion[Int]) -> (() -> Int) {
    || read(value)
}
```

```text
error[E1103]: cannot capture linear exclusive reference `value` in an escaping closure
```

## 6. Alternatives

### A. Do nothing

This keeps Region XOR as a capability-only rule and avoids new grammar, but
function signatures cannot express read-only versus writable access to a
region-owned value. It leaves the central API problem unresolved and makes
future compiler diagnostics less direct.

### B. Use only `&Region` and `&mut Region`

This is simpler to implement and matches the current prototype. It forces
callers to hand an entire region to helpers that use one value, increasing
aliasing surface and making APIs less local. It also does not provide a
uniform type for references to values nested inside structs or collections.

### C. Adopt Rust's full lifetime syntax

This gives maximum expression power and field-level precision, but introduces
named lifetime parameters, variance, lifetime elision rules, and a second
large type-system surface. It conflicts with NOVA's explicit decision that
region scope, not named lifetime syntax, is the source-level lifetime model.

### D. Use a capability lattice like Pony

A richer lattice can express more aliasing states and recovery patterns, but
it adds permissions that are not needed for NOVA's two promised operations:
shared reads and one exclusive writer. It would also make diagnostics and
inference substantially harder before the basic reference model is shipped.

## 7. Tradeoffs

- Region granularity rejects safe programs that borrow disjoint fields or
  collection elements concurrently.
- References add a new type constructor and borrow checker state to a
  language that previously had no source-level references.
- Inference can report a borrow conflict at a later use rather than exactly
  at the borrow expression when the conflict spans a call.
- Hidden region variables simplify source code but make some inferred
  relationships less visible until diagnostics explain them.
- Shared references are copyable, so the checker must track their count and
  region identity accurately; exclusive references remain linear to keep the
  writer case simple.

## 8. What this forecloses

If accepted, NOVA commits to `&T` meaning shared read access and `&mut T`
meaning unique write access. A future permission system cannot redefine those
spellings without a breaking language change.

The proposal also commits the first implementation to region-level
conflicts. Field-level borrow splitting, interior mutability, arbitrary
reference arithmetic, raw pointers, and references that outlive their source
regions remain unavailable unless a later RFC deliberately extends the model.

The proposal does not foreclose a future optimization that shortens borrows
to their last use, because that changes no source-level rule.

## 9. Costs

### Compile time

The checker adds borrow-state tracking and inferred region constraints. The
expected cost is linear in the number of borrow expressions and uses for the
lexical first implementation. Generic reference inference may add constraint
solving proportional to the number of connected borrow relationships.

### Runtime

The reference interpreter may represent a reference as a region identity plus
an object path and may maintain debug-only borrow counters. An optimized
backend can erase `&T` and `&mut T` after checking, retaining only the storage
address or frame offset needed by the target ABI. No garbage collector or
reference counting is required.

### Binary size

The static rules require no helper calls in optimized code. Debug builds may
include diagnostics and optional borrow assertions.

### Reader effort

The syntax is familiar, but users must understand the coarse region rule and
that `&mut T` is linear. This is lower than a full lifetime system but higher
than the current no-reference language.

## 10. Staging

### Stage 1: minimum shippable subset

1. Parse `&T`, `&mut T`, `&value`, and `&mut value`.
2. Permit reference parameters and local bindings.
3. Track shared/exclusive state at region granularity.
4. Enforce non-escape, move, write, and closure-capture rules.
5. Add accepted and rejected conformance tests for each diagnostic.
6. Integrate the scheduler handoff rule from the Region XOR runtime model.

### Stage 2: inferred return relationships

1. Infer hidden region variables for identity and projection helpers.
2. Permit returning a borrow tied to a live input region.
3. Add generic tests for references inside tuples, structs, and lists.

### Deferred

Field-level splitting, mutable collection elements, interior mutability,
raw pointers, reference cycles, arbitrary self-referential values, and named
lifetime syntax are deferred to separate RFCs.

## 11. Open questions

1. Should borrow scopes initially end only at lexical block exit, or should
   last-use shortening be part of the first user-facing implementation?
2. Should `&T` for immediate values be optimized away from the start, or
   should the reference interpreter expose one uniform runtime representation
   first?
3. Should storing a reference in a struct require an explicit constructor
   form, or is inferred region containment enough for diagnostics?
4. What syntax should expose an explicit early end for a long-lived shared
   borrow if lexical nesting is inconvenient?
5. Should task APIs accept `&T` directly, or require an explicit read-only
   message wrapper so concurrency crossing is visible at call sites?
6. Which existing type-system representation should carry the hidden region
   variable: a type-level parameter, an ownership side table, or both?

This RFC is intentionally a design proposal. It should not be marked
Accepted until the examples, diagnostic wording, and generic return rule have
received community review for at least the RFC process minimum of 14 days.
