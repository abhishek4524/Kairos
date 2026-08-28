"""
benchmark.py — Latency & Token Usage Benchmark: Single Big Agent vs Orchestrator + Sub-Agents.
"""

import csv
import json
import os
import sys
import time
from typing import Dict, List, Any

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_agent import get_system_prompt, GROQ_MODEL, LOOP_MODEL, groq_client
from agent_tools.registry import format_system_tools_prompt, TOOLS_SCHEMA
from agents.orchestrator import classify, get_agent_for_category, orchestrate

SAMPLE_REQUESTS = [
    # Coding
    {"category": "coding", "prompt": "write a Python quicksort algorithm in VS Code"},
    {"category": "coding", "prompt": "create a sandbox Python function to calculate fibonacci numbers"},
    # Browsing
    {"category": "browsing", "prompt": "open YouTube and search for lofi music"},
    {"category": "browsing", "prompt": "find flights from Delhi to Mumbai on MakeMyTrip"},
    # System Control
    {"category": "system_control", "prompt": "close calculator and open notepad"},
    {"category": "system_control", "prompt": "send a native WhatsApp Desktop message to Vansh saying hello"},
    # Research Memory
    {"category": "research_memory", "prompt": "what did I tell you about my preferred programming language?"},
    {"category": "research_memory", "prompt": "summarize my saved project notes about database architecture"},
    {"category": "chitchat_general", "prompt": "hello Kairos, how are you feeling today?"},
    {"category": "chitchat_general", "prompt": "what is the approximate distance from Earth to the Moon?"},
]


def estimate_tokens(text: str) -> int:
    """Rough token estimation heuristic (4 characters per token average)."""
    return max(1, len(text) // 4)


def run_benchmark():
    print("=" * 85)
    print(" KAIROS MULTI-AGENT ARCHITECTURE BENCHMARK ")
    print(" Comparing: Single Big Agent (~534 token tool prompt) vs Orchestrator + Sub-Agents ")
    print("=" * 85)

    single_agent_sys_prompt = get_system_prompt()
    single_prompt_tokens = estimate_tokens(single_agent_sys_prompt)
    print(f"\n[Baseline] Single Agent Full System Prompt Tokens: ~{single_prompt_tokens} tokens")

    results = []

    for idx, sample in enumerate(SAMPLE_REQUESTS, 1):
        prompt = sample["prompt"]
        expected_cat = sample["category"]

        print(f"\n--- [{idx}/10] Request: '{prompt}' ---")

        # ── BEFORE: Single Agent ──────────────────────────────────────────────
        t0 = time.time()
        before_prompt_tokens = single_prompt_tokens + estimate_tokens(prompt)
        before_resp_text = ""
        before_latency_ms = 0.0

        if groq_client:
            try:
                resp = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": single_agent_sys_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=60,
                    temperature=0.2,
                )
                before_latency_ms = (time.time() - t0) * 1000
                before_resp_text = resp.choices[0].message.content or ""
            except Exception as e:
                before_latency_ms = (time.time() - t0) * 1000
                before_resp_text = f"API Error: {e}"
        else:
            before_latency_ms = 120.0  # Mock fallback
            before_resp_text = "Mock response"

        before_total_tokens = before_prompt_tokens + estimate_tokens(before_resp_text)

        # ── AFTER: Orchestrator + Sub-Agent ───────────────────────────────────
        t_class_start = time.time()
        detected_cat, confidence = classify(prompt, groq_client=groq_client, model=GROQ_MODEL)
        class_latency_ms = (time.time() - t_class_start) * 1000

        sub_agent, effective_cat = get_agent_for_category(detected_cat, confidence)
        sub_sys_prompt = sub_agent.get_system_prompt()
        sub_prompt_tokens = estimate_tokens(sub_sys_prompt)

        # Classify call tokens + sub-agent call tokens
        classify_prompt_tokens = 220  # fixed few-shot classifier prompt
        after_prompt_tokens = classify_prompt_tokens + sub_prompt_tokens + estimate_tokens(prompt)

        t_gen_start = time.time()
        after_resp_text = ""
        after_gen_latency_ms = 0.0

        if groq_client:
            try:
                resp = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": sub_sys_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=60,
                    temperature=0.2,
                )
                after_gen_latency_ms = (time.time() - t_gen_start) * 1000
                after_resp_text = resp.choices[0].message.content or ""
            except Exception as e:
                after_gen_latency_ms = (time.time() - t_gen_start) * 1000
                after_resp_text = f"API Error: {e}"
        else:
            after_gen_latency_ms = 95.0
            after_resp_text = "Mock sub-agent response"

        after_total_latency_ms = class_latency_ms + after_gen_latency_ms
        after_total_tokens = after_prompt_tokens + estimate_tokens(after_resp_text)

        tokens_saved = single_prompt_tokens - sub_prompt_tokens

        row = {
            "id": idx,
            "prompt": prompt,
            "expected_category": expected_cat,
            "detected_category": detected_cat,
            "confidence": f"{confidence:.2f}",
            "agent_used": sub_agent.name,
            "before_sys_tokens": single_prompt_tokens,
            "after_sys_tokens": sub_prompt_tokens,
            "sys_tokens_saved": tokens_saved,
            "class_latency_ms": round(class_latency_ms, 1),
            "gen_latency_ms": round(after_gen_latency_ms, 1),
            "before_total_latency_ms": round(before_latency_ms, 1),
            "after_total_latency_ms": round(after_total_latency_ms, 1),
        }
        results.append(row)

        print(f"  Classified: {detected_cat} ({confidence:.2f}) -> {sub_agent.name} in {class_latency_ms:.1f}ms")
        print(f"  Sub-agent Sys Prompt Tokens: {sub_prompt_tokens} (saved {tokens_saved} tokens per turn)")
        print(f"  Latency — Before: {before_latency_ms:.1f}ms | After: {after_total_latency_ms:.1f}ms (classify: {class_latency_ms:.1f}ms)")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    csv_filename = os.path.join(os.path.dirname(__file__), "benchmark_results.csv")
    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    # ── Print Summary Table ───────────────────────────────────────────────────
    avg_class_lat = sum(r["class_latency_ms"] for r in results) / len(results)
    avg_tokens_saved = sum(r["sys_tokens_saved"] for r in results) / len(results)
    avg_before_lat = sum(r["before_total_latency_ms"] for r in results) / len(results)
    avg_after_lat = sum(r["after_total_latency_ms"] for r in results) / len(results)

    print("\n" + "=" * 85)
    print(" BENCHMARK SUMMARY REPORT ")
    print("=" * 85)
    print(f" Average Classification Latency (Target <150ms): {avg_class_lat:.1f} ms")
    print(f" Average System Prompt Tokens Saved per Sub-Agent Turn: ~{avg_tokens_saved:.0f} tokens")
    print(f" Average End-to-End Response Latency (Before vs After): {avg_before_lat:.1f}ms -> {avg_after_lat:.1f}ms")
    print(f" Results saved to: {csv_filename}")
    print("=" * 85)


if __name__ == "__main__":
    run_benchmark()
