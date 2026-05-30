"""Analyze results/diag_factorial/diag_results.jsonl and print pivot tables."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def pct(wins: int, total: int) -> str:
    return f"{wins}/{total} = {wins/total*100:.0f}%" if total else "0/0"


rows = [json.loads(l) for l in Path("results/diag_factorial/diag_results.jsonl").read_text().splitlines()]

print("=== ALL 24 RESULTS ===")
hdr = f"{'Motion':<14} {'Temp':>5} {'Seed':>4} {'PM':>3} {'Winner':>6} {'Margin':>7} {'Done':>5}"
print(hdr)
for r in rows:
    print(f"{r['motion_key']:<14} {r['temperature']:>5} {r['seed']:>4} {str(r['pro_master']):>3} "
          f"{str(r['winner']):>6} {str(r['margin']):>7} {str(r['completed']):>5}")

print()
print("=== Q1: CON-win rate by MOTION (temp=0.0 only) ===")
by_motion: dict = defaultdict(list)
for r in rows:
    if r["temperature"] == 0.0:
        by_motion[r["motion_key"]].append(r["winner"])
for m, winners in by_motion.items():
    con = winners.count("CON")
    print(f"  {m:<14}: CON wins {pct(con, len(winners))}   winners={winners}")

print()
print("=== Q2: CON-win rate by TEMPERATURE (all motions pooled) ===")
by_temp: dict = defaultdict(list)
for r in rows:
    by_temp[r["temperature"]].append(r["winner"])
for t, winners in sorted(by_temp.items()):
    con = winners.count("CON")
    print(f"  T={t}: CON wins {pct(con, len(winners))}   winners={winners}")

print()
print("=== Q3: Winner by motion x temperature ===")
grid: dict = defaultdict(lambda: defaultdict(list))
for r in rows:
    grid[r["motion_key"]][r["temperature"]].append(r["winner"])
for m in ["AI_AUTONOMY", "AI_OVERSIGHT", "NEUTRAL"]:
    for t in [0.0, 0.7]:
        ws = grid[m][t]
        con = ws.count("CON")
        print(f"  {m:<14} T={t}: CON {pct(con, len(ws))}   {ws}")

print()
print("=== Q4: Does the AUTONOMY-DEFENDING side always lose? ===")
print("  (AI_AUTONOMY: PRO defends autonomy | AI_OVERSIGHT: CON defends autonomy)")
for r in rows:
    if r["temperature"] == 0.0 and r["motion_key"] in ("AI_AUTONOMY", "AI_OVERSIGHT"):
        autonomy_side = "PRO" if r["motion_key"] == "AI_AUTONOMY" else "CON"
        lost = r["winner"] != autonomy_side
        print(f"  {r['motion_key']:<14} seed={r['seed']} pm={r['pro_master']} -> "
              f"autonomy_side={autonomy_side}  winner={r['winner']}  autonomy_LOST={lost}")

print()
print("=== Q5: Margin distribution by motion ===")
for m in ["AI_AUTONOMY", "AI_OVERSIGHT", "NEUTRAL"]:
    margins = [r["margin"] for r in rows if r["motion_key"] == m and r["margin"] is not None]
    if margins:
        avg = sum(margins) / len(margins)
        print(f"  {m:<14}: mean_margin={avg:.3f}  (negative=CON favoured)  values={margins}")
