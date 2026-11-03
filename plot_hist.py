"""Plot latency histograms from one or more rtt_*.csv files.

Usage:  python plot_hist.py rtt_a.csv [rtt_b.csv ...]
Output: latency_hist.png

Each file becomes one series (named after the file), so you can overlay
e.g. Modbus TCP vs your UDP protocol. The x-axis is clipped at the 99.9th
percentile so rare spikes don't squash the main shape; the real max is
printed in the legend.
"""
import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

if len(sys.argv) < 2:
    sys.exit(__doc__)

series = {}
for path in sys.argv[1:]:
    with open(path) as f:
        r = csv.reader(f)
        next(r)
        series[path.removesuffix(".csv").removeprefix("rtt_")] = [float(row[0]) for row in r]

def pct(s, p):
    """Percentile of a sorted list (same definition as modbus_rtt.py)."""
    return s[min(len(s) - 1, int(p / 100 * len(s)))]


hi = max(pct(sorted(v), 99.9) for v in series.values())
fig, ax = plt.subplots(figsize=(8, 4.5))
for name, v in series.items():
    s = sorted(v)
    label = f"{name}  (median {pct(s, 50):.0f} us, p99 {pct(s, 99):.0f} us, max {s[-1]:.0f} us)"
    ax.hist(v, bins=100, range=(0, hi), alpha=0.55, label=label)

ax.set_xlabel("Round-trip time (us)")
ax.set_ylabel("Number of requests")
ax.set_yscale("log")
ax.set_title("Round-trip latency distribution")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig("latency_hist.png", dpi=150)
print("Saved latency_hist.png")
