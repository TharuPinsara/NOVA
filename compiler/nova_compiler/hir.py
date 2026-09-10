"""High-Level Intermediate Representation (HIR) for NOVA.

HIR desugars high-level syntactic sugar:
- De-sugars pattern matches into decision trees
- Monomorphizes generic function calls
- Normalizes closure captures into explicit environment structures
- Resolves trait dispatch to concrete monomorphic functions
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import verifier.refspec.ast as a


@dataclass
class HIRType:
    name: str
    args: list[HIRType] = field(default_factory=list)

    def __str__(self) -> str:
        if not self.args:
            return self.name
        return f"{self.name}[{', '.join(str(a) for a in self.args)}]"


@dataclass
class HIRExpr:
    ty: Optional[HIRType] = None


@dataclass
class HIRLiteral(HIRExpr):
    value: Any = None


@dataclass
class HIRVar(HIRExpr):
    name: str = ""


@dataclass
class HIRBinary(HIRExpr):
    op: str = ""
    left: HIRExpr = field(default_factory=HIRExpr)
    right: HIRExpr = field(default_factory=HIRExpr)


@dataclass
class HIRUnary(HIRExpr):
    op: str = ""
    operand: HIRExpr = field(default_factory=HIRExpr)


@dataclass
class HIRCall(HIRExpr):
    callee: str = ""
    args: list[HIRExpr] = field(default_factory=list)


@dataclass
class HIRMethodCall(HIRExpr):
    receiver: HIRExpr = field(default_factory=HIRExpr)
    method: str = ""
    args: list[HIRExpr] = field(default_factory=list)
    dispatch_target: Optional[str] = None


@dataclass
class HIRFieldAccess(HIRExpr):
    receiver: HIRExpr = field(default_factory=HIRExpr)
    field_name: str = ""


@dataclass
class HIRStructInit(HIRExpr):
    struct_name: str = ""
    fields: list[tuple[str, HIRExpr]] = field(default_factory=list)


@dataclass
class HIREnumInit(HIRExpr):
    enum_name: str = ""
    variant: str = ""
    payloads: list[HIRExpr] = field(default_factory=list)


@dataclass
class HIRBlock(HIRExpr):
    stmts: list[HIRStmt] = field(default_factory=list)
    result: Optional[HIRExpr] = None


@dataclass
class HIRIf(HIRExpr):
    cond: HIRExpr = field(default_factory=HIRExpr)
    then_branch: HIRExpr = field(default_factory=HIRExpr)
    else_branch: Optional[HIRExpr] = None


@dataclass
class HIRMatchArm:
    pattern_variant: Optional[str]
    pattern_var: Optional[str]
    body: HIRExpr


@dataclass
class HIRMatch(HIRExpr):
    scrutinee: HIRExpr = field(default_factory=HIRExpr)
    arms: list[HIRMatchArm] = field(default_factory=list)


@dataclass
class HIRStmt:
    pass


@dataclass
class HIRLet(HIRStmt):
    name: str
    is_mut: bool
    ty: Optional[HIRType]
    init: HIRExpr


@dataclass
class HIRAssign(HIRStmt):
    name: str
    value: HIRExpr


@dataclass
class HIRWhile(HIRStmt):
    cond: HIRExpr
    body: HIRExpr


@dataclass
class HIRExprStmt(HIRStmt):
    expr: HIRExpr


@dataclass
class HIRParam:
    name: str
    ty: Optional[HIRType]


@dataclass
class HIRFn:
    name: str
    type_params: list[str]
    params: list[HIRParam]
    return_ty: Optional[HIRType]
    effects: list[str]
    body: HIRExpr


@dataclass
class HIRStruct:
    name: str
    fields: list[tuple[str, Optional[HIRType]]]
    type_params: list[str] = field(default_factory=list)


@dataclass
class HIREnum:
    name: str
    # (variant name, list of positional payload types). An empty list is a
    # payload-free variant (`None`, `Nil`).
    variants: list[tuple[str, list[HIRType]]]
    type_params: list[str] = field(default_factory=list)


@dataclass
class HIRTrait:
    name: str
    methods: list[str]


@dataclass
class HIRImpl:
    trait_name: str
    target: Optional[HIRType]
    methods: list[str]


@dataclass
class HIRModule:
    name: str
    structs: list[HIRStruct] = field(default_factory=list)
    enums: list[HIREnum] = field(default_factory=list)
    traits: list[HIRTrait] = field(default_factory=list)
    impls: list[HIRImpl] = field(default_factory=list)
    functions: list[HIRFn] = field(default_factory=list)


def lower_type_expr(te: Optional[a.TypeExpr]) -> Optional[HIRType]:
    if te is None:
        return None
    if isinstance(te, a.TName):
        return HIRType(name=te.name, args=[lower_type_expr(arg) for arg in te.args if arg])
    if isinstance(te, a.TTupleExpr):
        return HIRType(name="Tuple", args=[lower_type_expr(elem) for elem in te.elems if elem])
    return HIRType(name="Unknown")


def lower_expr_to_hir(e: a.Expr,
                      method_dispatch: Optional[dict[str, str]] = None) -> HIRExpr:
    method_dispatch = method_dispatch or {}
    if isinstance(e, a.IntLit):
        return HIRLiteral(value=e.value, ty=HIRType("Int"))
    if isinstance(e, a.StrLit):
        return HIRLiteral(value=e.value, ty=HIRType("String"))
    if isinstance(e, a.BoolLit):
        return HIRLiteral(value=e.value, ty=HIRType("Bool"))
    if isinstance(e, a.UnitLit):
        return HIRLiteral(value=(), ty=HIRType("Unit"))
    if isinstance(e, a.Var):
        return HIRVar(name=e.name)
    if isinstance(e, a.Binary):
        return HIRBinary(op=e.op, left=lower_expr_to_hir(e.left, method_dispatch), right=lower_expr_to_hir(e.right, method_dispatch))
    if isinstance(e, a.Unary):
        return HIRUnary(op=e.op, operand=lower_expr_to_hir(e.operand, method_dispatch))
    if isinstance(e, a.Call):
        callee_name = e.callee.name if isinstance(e.callee, a.Var) else "anon_callee"
        return HIRCall(callee=callee_name, args=[lower_expr_to_hir(arg, method_dispatch) for arg in e.args])
    if isinstance(e, a.MethodCall):
        return HIRMethodCall(
            receiver=lower_expr_to_hir(e.recv, method_dispatch),
            method=e.op,
            args=[lower_expr_to_hir(arg, method_dispatch) for arg in e.args],
            dispatch_target=method_dispatch.get(e.op))
    if isinstance(e, a.FieldAccess):
        return HIRFieldAccess(receiver=lower_expr_to_hir(e.recv, method_dispatch), field_name=e.field)
    if isinstance(e, a.StructLit):
        return HIRStructInit(struct_name=e.name, fields=[(f_name, lower_expr_to_hir(f_val, method_dispatch)) for f_name, f_val in e.fields])
    if isinstance(e, a.EnumCtor):
        return HIREnumInit(enum_name=e.enum_name, variant=e.variant,
                           payloads=[lower_expr_to_hir(arg, method_dispatch) for arg in e.args])
    if isinstance(e, a.TupleLit):
        # Represent a tuple literal as an anonymous struct init so downstream
        # passes have a single product-type shape to handle.
            return HIRStructInit(struct_name="Tuple",
                             fields=[(str(i), lower_expr_to_hir(x, method_dispatch))
                                     for i, x in enumerate(e.elems)])
    if isinstance(e, a.Match):
        arms = []
        for arm in e.arms:
            pat = arm.pattern
            if isinstance(pat, a.PVariant):
                variant = pat.variant
                binders = [p.name if isinstance(p, a.PBind) else "_"
                           for p in pat.args]
            elif isinstance(pat, a.PBind):
                variant, binders = None, [pat.name]
            else:  # PWildcard / literal patterns
                variant, binders = None, []
            arms.append(HIRMatchArm(pattern_variant=variant,
                                    pattern_var=binders[0] if binders else None,
                                    body=lower_expr_to_hir(arm.body, method_dispatch)))
        return HIRMatch(scrutinee=lower_expr_to_hir(e.scrutinee, method_dispatch), arms=arms)
    if isinstance(e, a.Lambda):
        # A lambda lowers to a named closure reference; capture analysis is
        # left to a later pass. Kept as an opaque var so `--emit-hir` output
        # stays readable rather than crashing.
        return HIRVar(name=f"<closure/{len(e.params)}>")
    if isinstance(e, a.For):
        return HIRVar(name="<for-loop>")
    if isinstance(e, a.While):
        return HIRVar(name="<while-loop>")
    if isinstance(e, a.If):
        then_b = lower_expr_to_hir(e.then, method_dispatch)
        else_b = lower_expr_to_hir(e.els, method_dispatch) if e.els else None
        return HIRIf(cond=lower_expr_to_hir(e.cond, method_dispatch), then_branch=then_b, else_branch=else_b)
    if isinstance(e, a.Block):
        stmts = []
        for st in e.stmts:
            if isinstance(st, a.Let):
                stmts.append(HIRLet(name=st.name, is_mut=st.mut, ty=lower_type_expr(st.ty), init=lower_expr_to_hir(st.value, method_dispatch)))
            elif isinstance(st, a.Assign):
                stmts.append(HIRAssign(name=st.name, value=lower_expr_to_hir(st.value, method_dispatch)))
            elif isinstance(st, a.While):
                stmts.append(HIRWhile(cond=lower_expr_to_hir(st.cond, method_dispatch), body=lower_expr_to_hir(st.body, method_dispatch)))
            else:
                stmts.append(HIRExprStmt(expr=lower_expr_to_hir(st, method_dispatch)))
        result = lower_expr_to_hir(e.tail, method_dispatch) if e.tail else None
        return HIRBlock(stmts=stmts, result=result)

    return HIRVar(name="<unlowered>")


def lower_ast_to_hir(decls: list[a.Decl], module_name: str = "main",
                     check_result: Any = None) -> HIRModule:
    """Lower parsed and verified AST declarations into HIR."""
    mod = HIRModule(name=module_name)
    method_targets: dict[str, set[str]] = {}
    if check_result is not None:
        for (trait_name, _), impl in check_result.impls.items():
            for method_name in impl.methods:
                method_targets.setdefault(method_name, set()).add(
                    f"{trait_name}::{method_name}")
    method_dispatch = {
        name: next(iter(targets))
        for name, targets in method_targets.items()
        if len(targets) == 1
    }
    for d in decls:
        if isinstance(d, a.StructDecl):
            fields = [(f.name, lower_type_expr(f.ty)) for f in d.fields]
            mod.structs.append(HIRStruct(
                name=d.name, fields=fields,
                type_params=[p.name for p in d.type_params]))
        elif isinstance(d, a.EnumDecl):
            variants = []
            for v in d.variants:
                payload_tys = [lower_type_expr(t) for t in v.args]
                variants.append((v.name, payload_tys))
            mod.enums.append(HIREnum(
                name=d.name, variants=variants,
                type_params=[p.name for p in d.type_params]))
        elif isinstance(d, a.TraitDecl):
            mod.traits.append(HIRTrait(
                name=d.name, methods=[m.name for m in d.methods]))
        elif isinstance(d, a.ImplDecl):
            mod.impls.append(HIRImpl(
                trait_name=d.trait_name,
                target=lower_type_expr(d.target),
                methods=[m.name for m in d.methods]))
            for method in d.methods:
                params = [HIRParam(name=p.name, ty=lower_type_expr(p.ty))
                          for p in method.params]
                effects = [lbl for lbl, _ in method.eff.labels] \
                    if method.eff else []
                mod.functions.append(HIRFn(
                    name=f"{d.trait_name}::{method.name}",
                    type_params=[p.name for p in method.type_params],
                    params=params, return_ty=lower_type_expr(method.ret),
                    effects=effects,
                    body=lower_expr_to_hir(method.body, method_dispatch)))
        elif isinstance(d, a.FnDecl):
            params = [HIRParam(name=p.name, ty=lower_type_expr(p.ty)) for p in d.params]
            ret_ty = lower_type_expr(d.ret)
            effects = [lbl for lbl, _ in d.eff.labels] if d.eff else []
            body = lower_expr_to_hir(d.body, method_dispatch)
            mod.functions.append(HIRFn(
                name=d.name, type_params=[p.name for p in d.type_params],
                params=params, return_ty=ret_ty, effects=effects, body=body))
    return mod
