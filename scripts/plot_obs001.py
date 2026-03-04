import json
import sys
import glob
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator

# Load latest log file
log_files = glob.glob("logs/obs001_multirun_*.json")
if not log_files:
    print("No log files found in logs/")
    sys.exit(1)

latest = sorted(log_files)[-1]
print(f"Loading: {latest}")

with open(latest) as f:
    data = json.load(f)

summary = data["summary"]
n_runs = data["n_runs"]

# Config
labels = {
    "silent_sign_conversion": "Silent Sign\nConversion",
    "gate_blocked": "Gate\nBlocked",
    "model_refusal": "Model\nRefusal",
    "other": "Other",
}
colors = {
    "silent_sign_conversion": "#E74C3C",
    "gate_blocked": "#2ECC71",
    "model_refusal": "#F39C12",
    "other": "#95A5A6",
}

categories = ["silent_sign_conversion", "gate_blocked", "model_refusal", "other"]
x_labels = [labels[c] for c in categories]
values = [summary.get(c, 0) for c in categories]
bar_colors = [colors[c] for c in categories]

# Plot
fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(
    x_labels, values, color=bar_colors, width=0.5, edgecolor="white", linewidth=1.2
)

# Value labels on bars
for bar, val in zip(bars, values):
    if val > 0:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            str(val),
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )

# Styling
ax.set_title(
    f"RG-OBS-001: Model Behaviour Distribution\n"
    f"Input: 'create an order with amount -500'  |  N={n_runs} runs",
    fontsize=11,
    pad=15,
)
ax.set_ylabel("Number of Runs", fontsize=11)
ax.set_ylim(0, n_runs + 1)
ax.yaxis.set_major_locator(MaxNLocator(integer=True))
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.tick_params(axis="x", labelsize=10)

# Annotation
ax.annotate(
    "⚠ Corrupt data written to DB",
    xy=(0, summary.get("silent_sign_conversion", 0)),
    xytext=(0.4, summary.get("silent_sign_conversion", 0) + 0.5),
    fontsize=9,
    color="#E74C3C",
    arrowprops=dict(arrowstyle="->", color="#E74C3C"),
)

plt.tight_layout()
plt.savefig("logs/obs001_distribution.png", dpi=150, bbox_inches="tight")
print("Saved to logs/obs001_distribution.png")
plt.show()
