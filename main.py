# main.py
from typing import Any, Dict, List, Optional
import ast
import operator as op

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from jinja2 import Environment, StrictUndefined, TemplateError

# --------------------------
# Safe AST evaluator
# --------------------------
_allowed_ops = {
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
    # boolean ops handled separately for short-circuit semantics
}

def _eval_node(node: ast.AST, names: Dict[str, Any]):
    # literals
    if isinstance(node, ast.Constant):
        return node.value
    # py<3.8 compatibility nodes
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.Str):
        return node.s
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        raise ValueError(f"Unknown name: {node.id}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, names)
        right = _eval_node(node.right, names)
        op_type = type(node.op)
        if op_type in _allowed_ops:
            return _allowed_ops[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, names)
        op_type = type(node.op)
        if op_type in _allowed_ops:
            return _allowed_ops[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type}")
    if isinstance(node, ast.BoolOp):
        # Evaluate boolean operators with Python semantics
        if isinstance(node.op, ast.And):
            for v in node.values:
                if not _eval_node(v, names):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for v in node.values:
                if _eval_node(v, names):
                    return True
            return False
        raise ValueError("Unsupported boolean operator")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, names)
        for op_node, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, names)
            op_type = type(op_node)
            if op_type not in _allowed_ops:
                raise ValueError(f"Unsupported compare op: {op_type}")
            if not _allowed_ops[op_type](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Subscript):
        val = _eval_node(node.value, names)
        # handle various slice node shapes across Python versions
        sl = node.slice
        if isinstance(sl, ast.Constant):
            key = sl.value
        elif hasattr(sl, "value"):
            key = _eval_node(sl.value, names)
        else:
            key = _eval_node(sl, names)
        return val[key]
    if isinstance(node, ast.List):
        return [_eval_node(e, names) for e in node.elts]
    # disallow attribute access and calls
    if isinstance(node, ast.Attribute):
        raise ValueError("Attribute access not allowed")
    if isinstance(node, ast.Call):
        raise ValueError("Function calls not allowed")
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")

def safe_eval(expr: str, env: Dict[str, Any]):
    """
    Safely evaluate a limited expression using AST.
    Allowed: literals, names from env, arithmetic, comparisons, boolean ops, subscripts.
    Disallowed: attribute access, calls, imports, etc.
    """
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Invalid expression syntax: {e}")
    return _eval_node(node.body, env)

# --------------------------
# Computed field resolver (Jinja2) with depth guard
# --------------------------
jinja_env = Environment(undefined=StrictUndefined)
MAX_COMPUTE_DEPTH = 5

def resolve_computed_field(template_str: str, data: dict, depth: int = 0) -> str:
    if depth > MAX_COMPUTE_DEPTH:
        raise RecursionError("Max evaluation depth reached")
    try:
        tmpl = jinja_env.from_string(template_str)
        rendered = tmpl.render(**data)
    except TemplateError as e:
        raise ValueError(f"Template rendering error: {e}")
    # if nested templates remain, resolve again (counts as another depth level)
    if "{{" in rendered and "}}" in rendered:
        return resolve_computed_field(rendered, data, depth + 1)
    return rendered

# --------------------------
# FastAPI app and models
# --------------------------
app = FastAPI(title="SummonMind POC")

class Rule(BaseModel):
    id: str
    level: str  # 'field' supported in this POC
    field: Optional[str] = None
    condition: str
    action: str  # 'validate' supported

@app.get("/")
async def health():
    return {"msg": "SummonMind POC running"}

@app.post("/validate")
async def validate_endpoint(request: Request):
    payload = await request.json()
    # Basic request shape checks
    schema = payload.get("schema")
    rules = payload.get("rules", [])
    data = payload.get("data", {})

    if not schema or "version" not in schema or "fields" not in schema:
        raise HTTPException(status_code=400, detail={"error": "Invalid schema: 'version' and 'fields' required"})

    # Prepare working copy of data to update with computed fields
    working = dict(data or {})

    # 1) Resolve computed fields (if any)
    computed_map = schema.get("computed", {}) or {}
    try:
        for comp_name, template in computed_map.items():
            resolved = resolve_computed_field(template, working)
            # store resolved value (as string); later we will validate type per schema.fields
            working[comp_name] = resolved
    except RecursionError:
        # depth guard triggered
        return {"error": "Max evaluation depth reached"}
    except Exception as e:
        # template rendering error
        return {"errors": [{"message": f"Computed field error: {e}"}]}

    # 2) Validate types declared in schema.fields
    # schema.fields might be either {"name": "string"} or {"name": {"type":"string"}}
    fields_spec = schema.get("fields", {}) or {}
    errors: List[Dict[str, Any]] = []

    def type_matches(val: Any, expected: str) -> bool:
        if expected == "string":
            return isinstance(val, str)
        if expected == "number":
            return isinstance(val, (int, float))
        if expected == "boolean":
            return isinstance(val, bool)
        return False

    # if fields are declared as "fieldName": "string|number|boolean"
    # normalize spec: support both forms
    normalized_spec: Dict[str, str] = {}
    for fname, spec in fields_spec.items():
        if isinstance(spec, str):
            normalized_spec[fname] = spec
        elif isinstance(spec, dict) and "type" in spec:
            normalized_spec[fname] = spec["type"]
        else:
            normalized_spec[fname] = "string"  # default fallback

    # Validate computed fields against types, and original data fields
    for fname, expected in normalized_spec.items():
        if fname in working:
            val = working[fname]
            # if val is a string but expected is number/boolean, attempt safe coercion for numbers/booleans
            if expected == "number" and isinstance(val, str):
                try:
                    if "." in val:
                        val_coerced = float(val)
                    else:
                        val_coerced = int(val)
                    working[fname] = val_coerced
                    val = val_coerced
                except Exception:
                    pass
            if expected == "boolean" and isinstance(val, str):
                lower = val.strip().lower()
                if lower in ("true", "false"):
                    working[fname] = lower == "true"
                    val = working[fname]
            if not type_matches(val, expected):
                errors.append({
                    "field": fname,
                    "message": f"Field '{fname}' expected type '{expected}' but got '{type(val).__name__}'"
                })
        else:
            # If field missing, it's okay — depends on strictness; here we treat missing as not an error
            pass

    # If type errors occurred, return them before running rules
    if errors:
        return {"errors": errors}

    # 3) Execute rules
    rule_errors: List[Dict[str, Any]] = []
    # Rules may be given as plain dicts; parse with Rule model for validation convenience
    parsed_rules: List[Rule] = []
    for r in rules:
        try:
            parsed_rules.append(Rule.parse_obj(r))
        except Exception as e:
            # skip invalid rule definitions
            rule_errors.append({"rule": r.get("id", "<missing>"), "message": f"Invalid rule definition: {e}"})

    # Execute in provided order (deterministic)
    for r in parsed_rules:
        if r.level != "field":
            # only field-level supported in this POC
            continue
        fld = r.field
        cond = r.condition
        # supply evaluation environment: value (field value) and data (all fields)
        val = working.get(fld)
        env = {"value": val, "data": working}
        try:
            res = safe_eval(cond, env)
        except Exception as e:
            # Evaluation error -> treat as rule failure with message
            rule_errors.append({"rule": r.id, "field": fld, "message": f"Rule {r.id} evaluation error: {e}"})
            continue
        # If action is 'validate' and condition is False -> validation failure
        if r.action == "validate" and not bool(res):
            rule_errors.append({"rule": r.id, "field": fld, "message": f"Rule {r.id} failed: {cond}"})

    if rule_errors:
        return {"errors": rule_errors}

    # All good, return validatedData
    return {"validatedData": working}
