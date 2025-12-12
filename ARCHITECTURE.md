# Architecture Documentation

## Overview

This service implements a schema validation and rule execution engine with computed field support. The architecture prioritizes simplicity, safety, and deterministic behavior.

## Schema Validation Approach

### Type System
The service supports three primitive types: `string`, `number`, and `boolean`. Type validation is performed using Python's runtime type checking with special handling for boolean/number disambiguation (booleans are excluded from number checks since `isinstance(True, int)` returns `True` in Python).

### Validation Flow
1. **Schema Version Check**: Ensures schema contains a valid version number
2. **Field Type Validation**: Iterates through schema fields and validates each data field against its expected type
3. **Early Return**: If any type mismatch occurs, validation stops and returns errors immediately
4. **Computed Field Resolution**: Only executed after successful type validation

### Design Rationale
- **Fail-fast**: Type errors are caught before rule execution to prevent cascading failures
- **Clear Error Messages**: Each type mismatch produces a descriptive error with field name and type information

## Rule Execution Model

### Rule Structure
Rules follow a declarative model with:
- `id`: Unique identifier for error reporting
- `level`: Currently supports "field" level rules
- `field`: Target field name
- `condition`: Python expression evaluated in a controlled environment
- `action`: Currently supports "validate" action

### Execution Process
1. **Rule Filtering**: Only field-level validation rules are processed
2. **Environment Setup**: Each rule evaluation creates an isolated environment containing:
   - `value`: The field's value
   - All data fields (for cross-field validation)
3. **Safe Evaluation**: Conditions are parsed and validated using Python's AST module
4. **Result Collection**: Failed rules accumulate in an error list

### Safety Mechanism
The `safe_eval()` function uses AST (Abstract Syntax Tree) parsing to:
- Whitelist allowed operations (comparisons, arithmetic, boolean logic)
- Prevent code injection by disallowing function calls, imports, and complex operations
- Ensure evaluation remains deterministic and side-effect free

## Computed Fields Resolution

### Template Syntax
Computed fields use mustache-style templates: `{{fieldName}}`

### Resolution Algorithm
1. **Topological Ordering**: Fields are processed in sorted order for determinism
2. **Recursive Substitution**: Templates can reference other computed fields
3. **Resolution Strategy**:
   - First checks user-provided data
   - Then checks previously resolved computed fields
   - Missing references resolve to empty string
4. **Depth Tracking**: Each recursive substitution increments depth counter

### Example Flow
```
computed: { "fullName": "{{firstName}} {{lastName}}" }
data: { "firstName": "Alice", "lastName": "Wonder" }

â†’ Resolves to: "Alice Wonder"
```

For nested templates:
```
computed: {
  "greeting": "Hello {{fullName}}",
  "fullName": "{{firstName}} {{lastName}}"
}

â†’ Iteration 1: fullName = "Alice Wonder"
â†’ Iteration 2: greeting = "Hello Alice Wonder"
```

## Recursion Prevention

### Depth Guard Implementation
- **Maximum Depth**: 5 levels (defined by `MAX_DEPTH` constant)
- **Tracking**: Each template substitution increments depth counter
- **Termination**: When depth exceeds limit, returns failure flag
- **Error Response**: Returns `{"error": "Max evaluation depth reached"}`

### Protection Against
- Circular references: `a = "{{b}}"`, `b = "{{a}}"`
- Deep nesting chains: `a â†’ b â†’ c â†’ d â†’ e â†’ f`
- Malicious payloads designed to cause resource exhaustion

### Design Choice
Depth limit of 5 balances:
- Reasonable use cases (most real-world scenarios need 1-2 levels)
- Protection against abuse
- Clear error messaging when limit is exceeded

## Determinism & Idempotency

### Deterministic Behavior
The service guarantees:
1. **Same Input â†’ Same Output**: Identical requests always produce identical responses
2. **Stable Field Ordering**: Computed fields are processed in sorted key order
3. **No Hidden State**: No database, cache, or external dependencies
4. **Reproducible Evaluation**: Safe eval restricts non-deterministic operations

### Idempotency
Multiple identical requests:
- Do not modify any server state
- Return identical validation results
- Can be safely retried without side effects

### Guarantees
- **No randomness**: No random number generation or timestamp-based logic
- **No side effects**: Rules cannot modify data, only validate
- **Pure functions**: All evaluation is stateless and referentially transparent

## Technology Choices

- **FastAPI**: Modern async framework with automatic OpenAPI documentation
- **Pydantic**: Request/response validation and serialization
- **AST Module**: Safe expression evaluation without `eval()` risks
- **Regex**: Template pattern matching with consistent behavior

## Trade-offs

| Decision | Benefit | Cost |
|----------|---------|------|
| AST-based eval | Safe from injection | Limited expression complexity |
| Sorted field processing | Deterministic order | Cannot optimize dependencies |
| Depth limit at 5 | Prevents infinite loops | May limit complex templates |
| Field-level rules only | Simple, focused scope | Cannot validate cross-record logic |

## Future Extensibility

The architecture supports future enhancements:
- **Transform rules**: Modify data instead of just validating
- **Record-level rules**: Validate across multiple fields
- **Custom validators**: Pluggable validation functions
- **Async rule execution**: Parallel rule evaluation for performance
