#!/usr/bin/env python3
"""Tests for the reference interpreter's own implementation properties
(verifier/refspec/eval.py) that are not language conformance —
tests/run_conformance.py stays the arbiter for what NOVA programs must
compute. A failure here is a bug in how the interpreter runs a program,
not in what the language says the program means.
"""
from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from verifier.refspec.driver import compile_source          # noqa: E402
from verifier.refspec.eval import Interpreter, NovaRuntimeError  # noqa: E402

# A NOVA program that recurses deep enough to exceed the interpreter's
# Python-backed call stack on any machine (see docs/known-issues.md I6).
# The exact depth at which this happens is implementation- and
# platform-dependent (Python version, stack size, sys.setrecursionlimit)
# — this test does not pin that number, only the *behavior* at the
# boundary: a clean NovaRuntimeError, never a raw RecursionError
# traceback escaping run_main().
_DEEP_RECURSION_SRC = """
import std.list;

fn sum_list(xs: List[Int]) -> Int {
    match xs {
        List::Cons(x, rest) => x + sum_list(rest),
        List::Nil => 0,
    }
}

fn build_list(n: Int) -> List[Int] {
    let mut xs = empty();
    let mut i = 0;
    while i < n {
        xs = prepend(i, xs);
        i = i + 1;
    }
    xs
}

fn main(rt: Runtime) -> Int ! {Runtime} {
    let xs = build_list(1000000);
    rt.print("built");
    sum_list(xs)
}
"""


def test_deep_recursion_raises_clean_runtime_error():
    unit = compile_source(_DEEP_RECURSION_SRC, name="<deep-recursion>")
    interp = Interpreter(unit.result)
    try:
        interp.run_main()
    except NovaRuntimeError as e:
        assert "recursion" in str(e).lower(), str(e)
    except RecursionError:
        raise AssertionError(
            "a RecursionError escaped run_main() uncaught — this must "
            "become a NovaRuntimeError, see eval.py's run_main() and "
            "docs/known-issues.md I6")
    else:
        raise AssertionError(
            "expected this program to exceed the interpreter's recursion "
            "depth and fail; it returned normally instead — either the "
            "depth ceiling moved far enough that 1,000,000 no longer "
            "reaches it (raise the count above), or run_main() stopped "
            "raising RecursionError at all")


def test_moderate_recursion_still_works():
    """A regression guard for the fix above: catching RecursionError in
    run_main() must not swallow ordinary, safely-shallow recursion."""
    src = _DEEP_RECURSION_SRC.replace("1000000", "50")
    unit = compile_source(src, name="<moderate-recursion>")
    interp = Interpreter(unit.result)
    value = interp.run_main()
    assert value == sum(range(50)), value
    assert interp.out == ["built"], interp.out


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    passed, failed = 0, 0
    for name, fn in tests:
        try:
            fn()
        except Exception:
            failed += 1
            print(f"  FAIL {name}")
            for line in traceback.format_exc().splitlines()[-3:]:
                print("       " + line)
        else:
            passed += 1
            print(f"  ok   {name}")
    print(f"\n{passed} passed, {failed} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
