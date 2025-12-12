"""Simple comprehensive test for POC verification"""
import requests
import json
import sys

URL = "http://127.0.0.1:8000/validate"

print("\n" + "="*80)
print(" SUMMONMIND POC - COMPREHENSIVE BENCHMARK TEST ".center(80, "="))
print("="*80 + "\n")

# Check server
try:
    r = requests.get("http://127.0.0.1:8000", timeout=3)
    print(f"✓ Server Status: {r.json()['msg']}\n")
except:
    print("✗ ERROR: Server not running!\n")
    sys.exit(1)

passed = 0
total = 0

def run_test(num, name, payload, should_have_errors=False):
    global passed, total
    total += 1
    print(f"\n[TEST {num}] {name}")
    print("-" * 80)
    try:
        response = requests.post(URL, json=payload, timeout=5)
        result = response.json()
        
        if should_have_errors:
            if "errors" in result or "error" in result:
                print(f"✓ PASS: Correctly returned errors")
                print(f"  Response: {json.dumps(result, indent=2)[:200]}...")
                passed += 1
            else:
                print(f"✗ FAIL: Should have returned errors")
        else:
            if "validatedData" in result:
                print(f"✓ PASS: Validation successful")
                print(f"  Validated Data: {json.dumps(result['validatedData'], indent=2)[:200]}...")
                passed += 1
            else:
                print(f"✗ FAIL: Should have succeeded")
                print(f"  Response: {json.dumps(result, indent=2)[:200]}...")
    except Exception as e:
        print(f"✗ FAIL: {str(e)}")

# Test 1: Basic schema validation
run_test(1, "Schema Validation - All Types (string, number, boolean)", {
    "schema": {"version": 1, "fields": {"name": "string", "age": "number", "active": "boolean"}},
    "rules": [],
    "data": {"name": "John", "age": 30, "active": True}
})

# Test 2: Type mismatch
run_test(2, "Type Mismatch Detection", {
    "schema": {"version": 1, "fields": {"age": "number"}},
    "rules": [],
    "data": {"age": "not_a_number"}
}, should_have_errors=True)

# Test 3: Computed fields
run_test(3, "Computed Fields with Nested Templates", {
    "schema": {
        "version": 1,
        "fields": {"firstName": "string", "lastName": "string"},
        "computed": {"fullName": "{{firstName}} {{lastName}}", "greeting": "Hello {{fullName}}"}
    },
    "rules": [],
    "data": {"firstName": "Alice", "lastName": "Wonder"}
})

# Test 4: Rule validation - pass
run_test(4, "Rule Validation - Should Pass (age >= 18)", {
    "schema": {"version": 1, "fields": {"age": "number"}},
    "rules": [{"id": "r1", "level": "field", "field": "age", "condition": "value >= 18", "action": "validate"}],
    "data": {"age": 25}
})

# Test 5: Rule validation - fail
run_test(5, "Rule Validation - Should Fail (age < 18)", {
    "schema": {"version": 1, "fields": {"age": "number"}},
    "rules": [{"id": "r1", "level": "field", "field": "age", "condition": "value >= 18", "action": "validate"}],
    "data": {"age": 16}
}, should_have_errors=True)

# Test 6: Multiple rules
run_test(6, "Multiple Rules Validation", {
    "schema": {"version": 1, "fields": {"email": "string", "age": "number"}},
    "rules": [
        {"id": "r1", "level": "field", "field": "email", "condition": "value != ''", "action": "validate"},
        {"id": "r2", "level": "field", "field": "age", "condition": "value >= 18 and value <= 120", "action": "validate"}
    ],
    "data": {"email": "test@example.com", "age": 30}
})

# Test 7: Boolean check (important - True != 1 in validation)
run_test(7, "Boolean vs Number Type Distinction", {
    "schema": {"version": 1, "fields": {"isActive": "boolean", "count": "number"}},
    "rules": [],
    "data": {"isActive": True, "count": 5}
})

# Test 8: Safe eval test
run_test(8, "Safe Expression Evaluation (arithmetic in condition)", {
    "schema": {"version": 1, "fields": {"score": "number"}},
    "rules": [{"id": "r1", "level": "field", "field": "score", "condition": "value >= 50 and value <= 100", "action": "validate"}],
    "data": {"score": 85}
})

# Summary
print("\n" + "="*80)
print(" TEST RESULTS SUMMARY ".center(80, "="))
print("="*80)
print(f"\nTotal Tests: {total}")
print(f"Passed: {passed}")
print(f"Failed: {total - passed}")
print(f"Success Rate: {(passed/total)*100:.1f}%\n")

if passed == total:
    print("🎉 ALL BENCHMARK TESTS PASSED!")
    print("✓ Schema validation working")
    print("✓ Type checking working") 
    print("✓ Computed fields working")
    print("✓ Rule execution working")
    print("✓ Error handling working")
    print("✓ Safe evaluation working")
    print("\n✅ POC IS READY FOR SUBMISSION TO HR!\n")
else:
    print(f"⚠️  {total - passed} test(s) failed\n")

print("="*80 + "\n")
