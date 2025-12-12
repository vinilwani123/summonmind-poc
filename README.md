# SummonMind POC - Schema Validation & Rule Engine

A minimal backend service that validates data against schemas and executes declarative rules with computed field support.

## Features

- Schema-based data validation (string, number, boolean types)
- Declarative rule engine with condition evaluation
- Computed fields with template substitution
- Depth guard to prevent infinite recursion (max depth: 5)
- Clean REST API with FastAPI

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd summonmind-poc
```

### 2. Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Server

Start the FastAPI server using uvicorn:

```bash
uvicorn main:app --reload
```

The server will start at `http://127.0.0.1:8001`

To verify the server is running:
```bash
curl http://127.0.0.1:8001/
```

Expected response: `{"msg":"SummonMind POC running"}`

## API Endpoint

### POST /validate

Validates data against a schema and executes rules.

**Request Body:**
```json
{
  "schema": {
    "version": 1,
    "fields": {
      "fieldName": "string|number|boolean"
    },
    "computed": {
      "computedField": "{{template}}"
    }
  },
  "rules": [
    {
      "id": "r1",
      "level": "field",
      "field": "fieldName",
      "condition": "value >= 18",
      "action": "validate"
    }
  ],
  "data": {
    "fieldName": "value"
  }
}
```

**Success Response:**
```json
{
  "validatedData": {
    "fieldName": "value",
    "computedField": "computed value"
  }
}
```

**Error Response:**
```json
{
  "errors": [
    {
      "rule": "r1",
      "field": "age",
      "message": "Rule r1 failed: value >= 18"
    }
  ]
}
```

## Sample curl Commands

### Test Valid Data

```bash
curl -X POST http://127.0.0.1:8001/validate \
  -H "Content-Type: application/json" \
  -d @samples/valid.json
```

Expected: Returns `validatedData` with computed fields

### Test Invalid Data

```bash
curl -X POST http://127.0.0.1:8001/validate \
  -H "Content-Type: application/json" \
  -d @samples/invalid.json
```

Expected: Returns `errors` array with validation failures

### Manual Test Example

```bash
curl -X POST http://127.0.0.1:8001/validate \
  -H "Content-Type: application/json" \
  -d '{
    "schema": {
      "version": 1,
      "fields": {
        "firstName": "string",
        "age": "number"
      },
      "computed": {
        "fullName": "{{firstName}} Smith"
      }
    },
    "rules": [
      {
        "id": "r1",
        "level": "field",
        "field": "age",
        "condition": "value >= 18",
        "action": "validate"
      }
    ],
    "data": {
      "firstName": "John",
      "age": 25
    }
  }'
```

## Running Tests

The repository includes an automated test script that validates both sample cases:

```bash
# Ensure the server is running in another terminal first
python test_samples.py
```

This will test:
1. `samples/valid.json` - Should pass all validations
2. `samples/invalid.json` - Should fail age validation (age < 18)

## Sample Files

- **samples/valid.json** - Contains valid data that passes all rules
- **samples/invalid.json** - Contains data with age=16 (fails the age >= 18 rule)

## Project Structure

```
summonmind-poc/
â”œâ”€â”€ main.py              # FastAPI application with validation logic
â”œâ”€â”€ requirements.txt     # Python dependencies
â”œâ”€â”€ README.md            # This file
â”œâ”€â”€ ARCHITECTURE.md      # Architecture documentation
â”œâ”€â”€ test_samples.py      # Automated test script
â”œâ”€â”€ samples/
â”‚   â”œâ”€â”€ valid.json       # Valid test case
â”‚   â””â”€â”€ invalid.json     # Invalid test case
```

## Error Handling

The service handles several error cases:

- **Schema Validation Errors**: Type mismatches return field-specific errors
- **Rule Validation Errors**: Failed conditions return rule-specific messages
- **Recursion Depth Exceeded**: Returns `"Max evaluation depth reached"`
- **Invalid Schema**: Returns 400 error if version is missing

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://127.0.0.1:8001/docs`
- ReDoc: `http://127.0.0.1:8001/redoc`

## License

This is a proof-of-concept assignment for SummonMind.
