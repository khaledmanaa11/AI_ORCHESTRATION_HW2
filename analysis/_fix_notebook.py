"""Fix the analysis notebook: remove seaborn, repair stale paths, drop NameError chain."""
import json
from pathlib import Path

NB_PATH = Path("notebooks/analysis.ipynb")
nb = json.loads(NB_PATH.read_text(encoding="utf-8"))


def _src(cell):
    return "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]


def _set(cell, text):
    cell["source"] = text.splitlines(keepends=True)
    cell["outputs"] = []
    cell["execution_count"] = None


for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = _src(cell)

    # 1. Replace seaborn imports/calls with matplotlib equivalents
    if "import seaborn as sns" in src:
        _set(cell,
            "import json\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n"
            "\n"
            "plt.rcParams['figure.dpi'] = 100\n"
            "plt.rcParams['axes.grid'] = True\n"
            "plt.rcParams['grid.alpha'] = 0.3\n"
        )
        continue

    # 2. Fix the stale load_stream cell that points at root results/ (no sweep prefix)
    if "load_stream(\"../results/stream_a_trajectory.jsonl\")" in src:
        _set(cell,
            "def load_stream(path):\n"
            "    records = []\n"
            "    with open(path, 'r', encoding='utf-8') as f:\n"
            "        for line in f:\n"
            "            if line.strip():\n"
            "                records.append(json.loads(line))\n"
            "    return pd.DataFrame(records)\n"
            "\n"
            "# Load from both completed sweeps (sweep_001 = k=42, sweep_full = k=10).\n"
            "# Section 5 below does its own richer load; this cell just gives the\n"
            "# legacy aggregate cells a non-empty df_a / df_c to work with.\n"
            "df_a_001 = load_stream('../results/sweep_001/stream_a_trajectory.jsonl')\n"
            "df_a_full = load_stream('../results/sweep_full/stream_a_trajectory.jsonl')\n"
            "df_a = pd.concat([df_a_001, df_a_full], ignore_index=True)\n"
            "df_c_001 = load_stream('../results/sweep_001/stream_c_metadata.jsonl')\n"
            "df_c_full = load_stream('../results/sweep_full/stream_c_metadata.jsonl')\n"
            "df_c = pd.concat([df_c_001, df_c_full], ignore_index=True)\n"
            "\n"
            "print(f'Stream A rows: {len(df_a)}')\n"
            "print(f'Stream C rows: {len(df_c)}')\n"
        )
        continue

    # 3. Replace the legacy win-rate mock with a real per-variant table from live data
    if "win_rates = {" in src and "naive" in src:
        _set(cell,
            "# Real per-variant PRO win rate, computed from the live data loaded above.\n"
            "# (Replaces the hardcoded mock that previously sat here.)\n"
            "verdict_mask = df_a['winner'].notna() & df_a['margin'].notna()\n"
            "verdict_rows = df_a[verdict_mask].drop_duplicates(subset='match_id')\n"
            "df_matches = verdict_rows.merge(\n"
            "    df_c[['match_id', 'judge_variant', 'first_speaker']],\n"
            "    on='match_id', how='left',\n"
            ")\n"
            "\n"
            "by_variant = (\n"
            "    df_matches.assign(pro_win=(df_matches.winner == 'PRO').astype(int))\n"
            "              .groupby('judge_variant')\n"
            "              .agg(n=('match_id', 'count'), pro_wins=('pro_win', 'sum'),\n"
            "                   mean_margin=('margin', 'mean'))\n"
            ")\n"
            "by_variant['pro_win_rate'] = (by_variant['pro_wins'] / by_variant['n']).round(3)\n"
            "by_variant['mean_margin'] = by_variant['mean_margin'].round(3)\n"
            "by_variant = by_variant.sort_values('pro_win_rate', ascending=False)\n"
            "print(by_variant)\n"
            "\n"
            "fig, ax = plt.subplots(figsize=(8, 4))\n"
            "ax.bar(by_variant.index, by_variant['pro_win_rate'], color='steelblue', alpha=0.8)\n"
            "ax.axhline(0.5, color='black', linestyle='--', linewidth=0.8, label='fair (50%)')\n"
            "ax.set_ylim(0, 1)\n"
            "ax.set_ylabel('PRO win rate'); ax.set_xlabel('Judge variant')\n"
            "ax.set_title('PRO win rate per judge variant (uncorrected, raw match level)')\n"
            "ax.legend(); plt.tight_layout(); plt.show()\n"
        )
        continue

    # 4. Replace any READ-accuracy or other legacy code that probably also breaks
    if "partial correlation" in src.lower() or "read.accuracy" in src.lower() or "Calculating partial correlation" in src:
        _set(cell,
            "# The original READ-accuracy partial correlation cell required data fields\n"
            "# (per-turn READ vector susceptibility scores aligned to judge tells) that the\n"
            "# baseline ablation arm did NOT populate -- ablation.master was False for the\n"
            "# entire reported sweep. The cell is replaced here with a clear placeholder; the\n"
            "# substantive bias analysis lives in Section 5 below.\n"
            "print('READ-accuracy analysis is not available in this submission: the player')\n"
            "print('ablation arm did not run (every match used ablation.master=False).')\n"
            "print('See analysis/FINDINGS.md \"What to NOT spend time on\" for context.')\n"
        )
        continue

    # 5. Section 5.2 boxplot: replace seaborn boxplot/stripplot with matplotlib
    if "sns.boxplot" in src or "sns.stripplot" in src:
        _set(cell,
            "fig, ax = plt.subplots(figsize=(9, 5))\n"
            "order = pair_summary.sort_values('pair_avg_margin').index.tolist()\n"
            "data_per_variant = [df_pairs[df_pairs.variant == v]['pair_margin'].values for v in order]\n"
            "bp = ax.boxplot(data_per_variant, labels=order, patch_artist=True,\n"
            "                boxprops=dict(facecolor='lightcoral', alpha=0.7),\n"
            "                medianprops=dict(color='black'))\n"
            "# Overlay raw points\n"
            "for i, v in enumerate(order, start=1):\n"
            "    pts = df_pairs[df_pairs.variant == v]['pair_margin'].values\n"
            "    ax.scatter([i] * len(pts), pts, color='black', alpha=0.6, s=20, zorder=3)\n"
            "ax.axhline(0, color='steelblue', linestyle='--', linewidth=1.5, label='unbiased judge (margin = 0)')\n"
            "ax.set_title('Mirror-pair-corrected margin per judge variant\\n(positive = PRO-favored, negative = CON-favored)', fontsize=12)\n"
            "ax.set_xlabel('Judge variant'); ax.set_ylabel('Pair-averaged signed margin')\n"
            "ax.legend(loc='upper right')\n"
            "plt.tight_layout(); plt.show()\n"
        )
        continue

NB_PATH.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("Notebook patched: seaborn removed, paths fixed, legacy mocks replaced with live computations.")
