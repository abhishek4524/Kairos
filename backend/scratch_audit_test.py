"""
scratch_audit_test.py — Automated Audit & Test Suite for Kavya Personal Assistant.
"""

import sys
import os
import io
import json
import time
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip().strip('"\'')

results = {}

print("=" * 60)
print("RUNNING KAVYA SYSTEM AUDIT TEST SUITE (EXACT API CHECKS)")
print("=" * 60)

# -------------------------------------------------------------
# Test 1: ChromaDB Memory Store & Retrieval
# -------------------------------------------------------------
print("\n[TEST 1] ChromaDB Long-Term Memory...")
try:
    import memory_store
    test_uid = "audit_test_user_999"
    # Store a test fact using upsert_fact
    fact_id = memory_store.upsert_fact(test_uid, "User preferences: Abhishek prefers Python and dark mode theme.")
    # Retrieve
    context = memory_store.retrieve_context(test_uid, "What is my preferred programming language?", top_k=3)
    # Cleanup test fact
    memory_store.delete_memory("facts", fact_id)
    
    if "Python" in context or "dark mode" in context:
        results["Memory & RAG"] = ("PASS", f"ChromaDB retrieval matched fact correctly.")
        print(f"  ✅ PASS: ChromaDB semantic search returned: {context}")
    else:
        results["Memory & RAG"] = ("FAIL", f"Fact retrieval context mismatch: '{context}'")
        print(f"  ❌ FAIL: ChromaDB retrieval failed.")
except Exception as e:
    results["Memory & RAG"] = ("FAIL", str(e))
    print(f"  ❌ FAIL: {e}")

# -------------------------------------------------------------
# Test 2: Code Sandbox Runner
# -------------------------------------------------------------
print("\n[TEST 2] Code Sandbox Execution...")
try:
    import sandbox_runner
    py_code = "print(sum([x**2 for x in range(1, 6)]))" # 1+4+9+16+25 = 55
    res = sandbox_runner.execute_code(py_code, language="python", timeout_sec=5)
    
    if res.get("status") == "success" and "55" in res.get("stdout", ""):
        results["Code Sandbox"] = ("PASS", f"Ran in {res.get('execution_time_ms')}ms. Output: {res.get('stdout').strip()}")
        print(f"  ✅ PASS: Sandbox ran in {res.get('execution_time_ms')}ms with stdout '{res.get('stdout').strip()}'.")
    else:
        results["Code Sandbox"] = ("FAIL", f"Sandbox error: {res}")
        print(f"  ❌ FAIL: Sandbox result: {res}")
except Exception as e:
    results["Code Sandbox"] = ("FAIL", str(e))
    print(f"  ❌ FAIL: {e}")

# -------------------------------------------------------------
# Test 3: OS Automation Tool Registry & Executor
# -------------------------------------------------------------
print("\n[TEST 3] OS Automation Executor...")
try:
    from agent_tools.executor import extract_action, strip_action_tag, APP_MAP, CLOSE_MAP
    
    # Test JSON extraction
    sample_tag = '[approval] [ACTION:{"tool":"open_app","params":{"app_name":"calculator"},"summary":"Open Calculator"}] Opening calculator for you!'
    action = extract_action(sample_tag)
    clean_text = strip_action_tag(sample_tag)
    
    # Check tool dictionary coverage
    has_calc = "calculator" in APP_MAP
    has_explorer = "file explorer" in APP_MAP
    has_brave = "brave browser" in APP_MAP
    has_close_calc = "calculator" in CLOSE_MAP
    
    if action and action.get("tool") == "open_app" and has_calc and has_explorer and has_brave and has_close_calc:
        results["OS Automation"] = ("PASS", f"Extracted '{action['tool']}' with params {action['params']}. All app keys mapped.")
        print(f"  ✅ PASS: Action parsing & mapping verified. Extracted: {action['tool']} -> {action['params']}")
    else:
        results["OS Automation"] = ("FAIL", f"Action parsing or map missing: action={action}")
        print("  ❌ FAIL: Action parsing or app map failed.")
except Exception as e:
    results["OS Automation"] = ("FAIL", str(e))
    print(f"  ❌ FAIL: {e}")

# -------------------------------------------------------------
# Test 4: STT Silence & Hallucination Filter Logic
# -------------------------------------------------------------
print("\n[TEST 4] STT Silence & Hallucination Filtering...")
try:
    from transcriber import RealTimeTranscriber
    
    transcriber = RealTimeTranscriber()
    # Feed 10 consecutive chunks of pure digital silence (float32 zeros at 16kHz)
    # Each chunk is 0.5s = 8000 samples
    chunk_samples = 8000
    silence_float32 = np.zeros(chunk_samples, dtype=np.float32).tobytes()
    
    emitted_transcripts = []
    for i in range(20): # 10 seconds of pure silence
        res = transcriber.process_audio_chunk(silence_float32, expected_lang="en")
        if res:
            emitted_transcripts.append(res)
            
    if len(emitted_transcripts) == 0:
        results["STT Silence Filter"] = ("PASS", "10 seconds of continuous silence produced ZERO phantom text across 20 chunks.")
        print("  ✅ PASS: 10s of continuous silence produced 0 hallucinations.")
    else:
        results["STT Silence Filter"] = ("FAIL", f"Silence emitted transcripts: {emitted_transcripts}")
        print(f"  ❌ FAIL: Silence hallucination: {emitted_transcripts}")
except Exception as e:
    results["STT Silence Filter"] = ("FAIL", str(e))
    print(f"  ❌ FAIL: {e}")

# -------------------------------------------------------------
# Summary Output
# -------------------------------------------------------------
print("\n" + "=" * 60)
print("AUDIT SUMMARY RESULTS")
print("=" * 60)
for k, v in results.items():
    icon = "✅" if v[0] == "PASS" else "🟡" if v[0] == "PARTIAL" else "❌"
    print(f"{icon} {k:25}: {v[0]} — {v[1]}")
