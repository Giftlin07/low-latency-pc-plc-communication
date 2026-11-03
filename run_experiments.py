"""Run the full "latency vs CPU load" experiment in one command.

For each load level (idle, 25%, 50%, 100% of your CPU cores) it runs the
Modbus RTT measurement several times, starting and stopping the CPU load
itself. Repeats are interleaved (idle, 25%, 50%, 100%, idle, 25%, ...) so a
slow drift on your machine, like thermal throttling, doesn't bias one level.

Needs modbus_rtt.py, modbus_sim_server.py, load_gen.py and plot_hist.py in
the same folder as this file.

Usage:
  python run_experiments.py                      # defaults: 10000 req, 3 repeats
  python run_experiments.py --count 20000 --repeats 5 --regs 100
  python run_experiments.py --no-server --host 192.168.1.10 --port 502
      (measure a real device / OpenPLC instead of the built-in simulator)

Output (in ./results_<regs>regs/):
  rtt_<level>_r<k>.csv   raw samples of every run
  summary.csv            one row per run: median, p99, p99.9, max, jitter
  latency_by_load.png    histogram overlay, all repeats pooled per level
"""
import argparse
import csv
import os
import signal
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=5020)
ap.add_argument("--count", type=int, default=10000, help="requests per run")
ap.add_argument("--regs", type=int, default=10, help="registers per request")
ap.add_argument("--repeats", type=int, default=3)
ap.add_argument("--levels", default="0,25,50,100",
                help="CPU load levels in percent of cores, comma separated")
ap.add_argument("--no-server", action="store_true",
                help="don't start the built-in simulator (target is already running)")
args = ap.parse_args()

cores = os.cpu_count() or 1
levels = [int(x) for x in args.levels.split(",")]
outdir = os.path.join(os.getcwd(), f"results_{args.regs}regs")
os.makedirs(outdir, exist_ok=True)


def pct(s, p):
    return s[min(len(s) - 1, int(p / 100 * len(s)))]


def level_name(pc):
    return "idle" if pc == 0 else f"load{pc}pct"


def start_load(workers):
    """Start the load generator in its own process group so we can kill it cleanly."""
    return subprocess.Popen(
        [PY, os.path.join(HERE, "load_gen.py"), str(workers), "0"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)


def stop_load(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    proc.wait()


server = None
if not args.no_server:
    server = subprocess.Popen(
        [PY, os.path.join(HERE, "modbus_sim_server.py"), args.host, str(args.port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)

print(f"Cores: {cores} | levels: {levels}% | {args.repeats} repeats x {args.count} requests "
      f"x {args.regs} registers")
rows = []
pooled = {lv: [] for lv in levels}
try:
    for rep in range(1, args.repeats + 1):
        for pc in levels:
            name = level_name(pc)
            workers = 0 if pc == 0 else max(1, round(cores * pc / 100))
            load = start_load(workers) if workers else None
            time.sleep(2.0 if workers else 0.5)       # let the load ramp up
            label = f"{name}_r{rep}"
            print(f"  repeat {rep}/{args.repeats}  {name:>9}  ({workers} busy workers) ...", flush=True)
            res = subprocess.run(
                [PY, os.path.join(HERE, "modbus_rtt.py"), args.host, str(args.port),
                 str(args.count), str(args.regs), label],
                cwd=outdir, capture_output=True, text=True)
            if load:
                stop_load(load)
            csv_path = os.path.join(outdir, f"rtt_{label}.csv")
            if res.returncode != 0 or not os.path.exists(csv_path):
                sys.exit(f"Measurement failed:\n{res.stdout}\n{res.stderr}")
            with open(csv_path) as f:
                r = csv.reader(f)
                next(r)
                v = sorted(float(x[0]) for x in r)
            pooled[pc].extend(v)
            rows.append({
                "level": name, "repeat": rep, "workers": workers, "n": len(v),
                "median_us": round(pct(v, 50), 1), "p99_us": round(pct(v, 99), 1),
                "p999_us": round(pct(v, 99.9), 1), "max_us": round(v[-1], 1),
                "jitter_std_us": round(statistics.pstdev(v), 1)})
finally:
    if server:
        server.terminate()

with open(os.path.join(outdir, "summary.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# pooled CSVs -> one histogram overlay
pooled_files = []
for pc in levels:
    p = os.path.join(outdir, f"rtt_{level_name(pc)}_all.csv")
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rtt_us"])
        w.writerows([[x] for x in pooled[pc]])
    pooled_files.append(os.path.basename(p))
subprocess.run([PY, os.path.join(HERE, "plot_hist.py"), *pooled_files], cwd=outdir,
               stdout=subprocess.DEVNULL, check=True)
os.replace(os.path.join(outdir, "latency_hist.png"), os.path.join(outdir, "latency_by_load.png"))

print("\nSummary: median / p99 across repeats (min-max of p99 in brackets), microseconds")
print(f"{'level':>10} {'median':>8} {'p99':>8} {'p99 range':>16} {'max':>8}")
for pc in levels:
    sel = [r for r in rows if r["level"] == level_name(pc)]
    p99s = [r["p99_us"] for r in sel]
    print(f"{level_name(pc):>10} {statistics.mean(r['median_us'] for r in sel):8.1f} "
          f"{statistics.mean(p99s):8.1f} {f'[{min(p99s):.0f}-{max(p99s):.0f}]':>16} "
          f"{max(r['max_us'] for r in sel):8.1f}")
print(f"\nSaved to {outdir}")
