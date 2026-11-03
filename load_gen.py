"""CPU load generator for repeatable "variable workload" experiments.

Starts N busy-loop processes that keep N CPU cores busy for a fixed time
(or until you press Ctrl+C). Run it in one terminal while modbus_rtt.py
runs in another, then compare the histograms.

Usage:  python load_gen.py [workers] [seconds]

  workers   default 4    how many cores to keep busy
  seconds   default 60   how long to run (0 = until Ctrl+C)

Tip: your Mac's core count is printed at start. Try 25%, 50% and 100%
of it as separate runs, and label each result accordingly, e.g.
  python3 modbus_rtt.py 127.0.0.1 5020 10000 10 load50pct
"""
import multiprocessing as mp
import sys
import time


def burn(stop_at):
    x = 0
    while stop_at == 0 or time.time() < stop_at:
        x = (x * 31 + 7) % 1000003   # pointless arithmetic that keeps the core busy


if __name__ == "__main__":
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    stop_at = time.time() + seconds if seconds > 0 else 0

    print(f"CPU cores available: {mp.cpu_count()}")
    print(f"Starting {workers} busy workers for {'until Ctrl+C' if seconds == 0 else f'{seconds} s'}")
    procs = [mp.Process(target=burn, args=(stop_at,), daemon=True) for _ in range(workers)]
    for p in procs:
        p.start()
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        print("\nStopping load")
    print("Load finished")
