"""Benchmark local models and the agent chain on the current machine.

Usage: .venv/Scripts/python scripts/benchmark.py [--runs 3] [--out data/evaluation/benchmark.json]

Measures (1) raw Ollama throughput per model on a fixed prompt and (2) end-to-end latency of the
n8n assistant webhook per agent path. Queries are user questions, not administrative content.
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.settings import get_settings  # noqa: E402

OLLAMA = get_settings().ollama_url.rstrip("/")  # OLLAMA_URL env var > .env > settings default
WEBHOOK = "http://localhost:5678/webhook/assistant"
MODELS = ["mistral:latest", "translategemma:4b"]
LLM_PROMPT = "Translate into English, output only the translation:\n1. Quittance de paiement du droit de timbre fiscal dû\n2. Joindre l'ancien passeport en cas de renouvellement"
CASES = [
    ("checklist_fr", {"text": "Quelles pièces fournir pour renouveler un passeport ?"}),
    ("checklist_derja", {"text": "شنوة الأوراق اللازمة باش نجدد الباسبور؟"}),
    ("checklist_en_translated", {"text": "What documents do I need to renew my passport?"}),
    ("rne_fee_table", {"text": "Combien coûte l'immatriculation d'une SARL au RNE ?"}),
    ("grounded_answer_en", {"text": "What is the penalty for late registration with the RNE?"}),
    ("router_llm_fallback", {"text": "quelle est la météo demain"}),
]


def gpu_info() -> str:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def bench_model(model: str, runs: int) -> dict:
    results = []
    for i in range(runs):
        r = httpx.post(f"{OLLAMA}/api/generate", json={"model": model, "prompt": LLM_PROMPT, "stream": False,
                       "options": {"temperature": 0, "num_predict": 120}, "keep_alive": "5m"}, timeout=600).json()
        results.append({
            "load_s": round(r.get("load_duration", 0) / 1e9, 2),
            "total_s": round(r.get("total_duration", 0) / 1e9, 2),
            "gen_tokens_per_s": round(r.get("eval_count", 0) / max(r.get("eval_duration", 1) / 1e9, 1e-9), 1),
        })
    ps = httpx.get(f"{OLLAMA}/api/ps", timeout=10).json().get("models", [])
    loaded = next((m for m in ps if m["name"] == model), {})
    vram = loaded.get("size_vram")
    size = loaded.get("size")
    return {"runs": results, "gpu_share": round(vram / size, 2) if vram and size else None,
            "warm_tokens_per_s_median": statistics.median(x["gen_tokens_per_s"] for x in results[1:] or results)}


def bench_chain(runs: int) -> dict:
    out = {}
    for name, payload in CASES:
        times, agent = [], None
        for _ in range(runs):
            t = time.perf_counter()
            r = httpx.post(WEBHOOK, json=payload, timeout=900)
            times.append(round(time.perf_counter() - t, 2))
            agent = r.json().get("agent")
        out[name] = {"agent": agent, "seconds": times, "median_s": statistics.median(times)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default="data/evaluation/benchmark.json")
    args = ap.parse_args()
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "machine": {"platform": platform.platform(), "processor": platform.processor(), "gpu": gpu_info()},
        "models": {m: bench_model(m, args.runs) for m in MODELS},
        "chain": bench_chain(args.runs),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
