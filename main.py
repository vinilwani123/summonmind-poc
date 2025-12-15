# main.py
from typing import Any, Dict, List, Optional
import ast
import operator as op

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from jinja2 import Environment, StrictUndefined, TemplateError

# =========================================================
# Safe AST Evaluator (for rule conditions)
# =========================================================

_ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.UAdd: lambda x: x,
    ast.USub: op.neg,
    ast.Eq: op.eq,
    ast.NotEq: op.ne,
    ast.Lt: op.lt,
    ast.LtE: op.le,
    ast.Gt: op.gt,
    ast.GtE: op.ge,
}

def _eval_node(node: ast.AST, env: Dict[str, Any]):
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise ValueError(f"Unknown variable: {node.id}")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, env)
        right = _eval_node(node.right, env)
        op_type = type(node.op)
        if op_type in _ALLOWED_OPS:
            return _ALLOWED_OPS[op_type](left, right)
        raise ValueError("Unsupported binary operator")

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, env)
        op_type = type(node.op)
        if op_type in _ALLOWED_OPS:
            return _ALLOWED_OPS[op_type](operand)
        raise ValueError("Unsupported unary operator")

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, env) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, env) for v in node.values)
        raise ValueError("Unsupported boolean operator")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, env)
        for op_node, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, env)
            op_type = type(op_node)
            if op_type not in _ALLOWED_OPS:
                raise ValueError("Unsupported comparison operator")
            if not _ALLOWED_OPS[op_type](left, right):
                return False
            left = right
        return True

    raise ValueError(f"Unsupported expression element: {type(node).__name__}")

def safe_eval(expr: str, env: Dict[str, Any]) -> bool:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ValueError("Invalid expression syntax")
    return _eval_node(tree.body, env)

# =========================================================
# Computed Fields (Jinja2) with Depth Guard
# =========================================================

jinja_env = Environment(undefined=StrictUndefined)
MAX_COMPUTE_DEPTH = 5

def resolve_computed(template: str, data: Dict[str, Any], depth: int = 0) -> str:
    if depth > MAX_COMPUTE_DEPTH:
        raise RecursionError("Max evaluation depth reached")

    try:
        rendered = jinja_env.from_string(template).render(**data)
    except TemplateError as e:
        raise ValueError(f"Template error: {e}")

    if "{{" in rendered and "}}" in rendered:
        return resolve_computed(rendered, data, depth + 1)

    return rendered

# =========================================================
# FastAPI App
# =========================================================

app = FastAPI(title="SummonMind Backend POC")

class Rule(BaseModel):
    id: str
    level: str
    field: Optional[str]
    condition: str
    action: str

@app.get("/")
async def health():
    return {"msg": "SummonMind POC running"}

@app.post("/validate")
async def validate_endpoint(request: Request):
    # ---------- Parse JSON safely ----------
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid or empty JSON body"}
        )

    schema = payload.get("schema")
    rules = payload.get("rules", [])
    data = payload.get("data", {})

    if not schema or "version" not in schema or "fields" not in schema:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid schema: version and fields required"}
        )

    # ---------- Working copy ----------
    working = dict(data)

    # ---------- Resolve computed fields ----------
    try:
        for name, template in (schema.get("computed") or {}).items():
            working[name] = resolve_computed(template, working)
    except RecursionError:
        return {"error": "Max evaluation depth reached"}
    except Exception as e:
        return {"errors": [{"message": str(e)}]}

    # ---------- Type validation ----------
    errors: List[Dict[str, Any]] = []

    def matches_type(val, expected):
        if expected == "string":
            return isinstance(val, str)
        if expected == "number":
            return isinstance(val, (int, float))
        if expected == "boolean":
            return isinstance(val, bool)
        return False

    for field, expected in schema["fields"].items():
        if field in working and not matches_type(working[field], expected):
            errors.append({
                "field": field,
                "message": f"Expected {expected}, got {type(working[field]).__name__}"
            })

    if errors:
        return {"errors": errors}

    # ---------- Execute rules ----------
    rule_errors = []

    for r in rules:
        rule = Rule(**r)

        if rule.level != "field":
            continue

        value = working.get(rule.field)
        env = {"value": value}

        try:
            passed = safe_eval(rule.condition, env)
        except Exception as e:
            rule_errors.append({
                "rule": rule.id,
                "field": rule.field,
                "message": str(e)
            })
            continue

        if rule.action == "validate" and not passed:
            rule_errors.append({
                "rule": rule.id,
                "field": rule.field,
                "message": f"Rule {rule.id} failed: {rule.condition}"
            })

    if rule_errors:
        return {"errors": rule_errors}

    return {"validatedData": working}
