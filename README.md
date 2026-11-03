# PC-to-PLC Communication Latency Study

A reproducible Python-based measurement study of Modbus TCP round-trip time (RTT) under controlled CPU load, with a minimal UDP echo experiment as an initial reference point for future lightweight industrial-communication research.

> **Important scope note:** The measurements currently committed here were collected using a Python client and a simulated Modbus TCP server over loopback on the same macOS computer. They do **not** represent measurements from a physical PLC or an Ethernet network. Treat the numbers as a software/simulator baseline only.

## Research questions

1. How does request-response latency change as CPU load increases?
2. How does the requested Modbus holding-register count affect measured RTT?
3. How do tail latency and variability behave compared with the median?
4. What measurement and protocol work is needed before a fair Modbus TCP vs. lightweight UDP comparison can be made?

## Repository contents

| Path | Description |
|---|---|
| `modbus_rtt.py` | Sends Modbus TCP Read Holding Registers (function code 3) requests and records per-request RTT samples. |
| `modbus_sim_server.py` | Minimal Modbus TCP simulator for local testing; not a physical PLC. |
| `load_gen.py` | Starts CPU busy-loop worker processes. |
| `run_experiments.py` | Automates repeated measurements at idle, 25%, 50%, and 100% nominal CPU-worker levels. |
| `plot_hist.py` | Creates latency-distribution histograms from RTT CSV files. |
| `udp_echo_server.py` | Minimal UDP echo endpoint. |
| `udp_rtt_client.py` | Measures UDP echo RTT and records samples. |
| `results/results_10regs/` | Raw and pooled samples, run summaries, and plot for 10-register requests. |
| `results/results_100regs/` | Raw and pooled samples, run summaries, and plot for 100-register requests. |

## Environment and dependencies

- Python 3
- macOS was used for the committed experiment runs.
- `matplotlib` is required only for plotting.
- The Modbus measurement and experiment scripts otherwise use the Python standard library.

Install the plotting dependency:

```bash
python3 -m pip install -r requirements.txt
```

## Reproduce the Modbus simulator experiments

Run from the repository root:

```bash
# 10 registers per request; five repeats; 10,000 timed requests per repeat
python3 run_experiments.py --repeats 5 --count 10000 --regs 10

# 100 registers per request
python3 run_experiments.py --repeats 5 --count 10000 --regs 100
```

By default, the script starts the local simulator on `127.0.0.1:5020`. It performs 200 warm-up requests before recording each run. Results are written to `results_<N>regs/` in the current working directory.

To run a single measurement manually, use two terminals:

```bash
# Terminal 1
python3 modbus_sim_server.py

# Terminal 2
python3 modbus_rtt.py 127.0.0.1 5020 10000 10 manual_run
python3 plot_hist.py rtt_manual_run.csv
```

The simulator binds to loopback by default. Do not expose it to an untrusted network.

## Measurement method

- One outstanding request at a time over one persistent TCP connection.
- Modbus TCP Read Holding Registers (function code 3).
- `TCP_NODELAY` enabled on the client and simulator sockets.
- `time.perf_counter_ns()` used for client-side timing.
- 200 warm-up requests discarded; 10,000 timed requests recorded per run.
- Five repeats per CPU-load level, with load levels interleaved in each repeat.
- CPU load is approximated using 0, 25, 50, or 100 percent of the machine's reported logical CPU count as busy-loop worker processes.
- Reported metrics include median, p99, p99.9, maximum, and population standard deviation (labelled `jitter_std_us` in the CSV).

The load percentages are worker-count targets, not calibrated measurements of total system CPU utilisation.

## Results

Each register-count experiment contains five runs per load level, giving 50,000 recorded request-response samples per level when pooled. The table below reports percentiles computed from the pooled raw samples, rounded to one decimal place.

### 10 registers per request

| CPU worker level | Samples | Median RTT (µs) | p99 RTT (µs) | p99.9 RTT (µs) | Maximum RTT (µs) |
|---:|---:|---:|---:|---:|---:|
| Idle | 50,000 | 27.0 | 51.9 | 74.2 | 109.5 |
| 25% | 50,000 | 28.7 | 77.5 | 112.7 | 1,082.6 |
| 50% | 50,000 | 26.5 | 106.9 | 159.2 | 1,359.7 |
| 100% | 50,000 | 20.2 | 172.5 | 572.8 | 3,012.1 |

### 100 registers per request

| CPU worker level | Samples | Median RTT (µs) | p99 RTT (µs) | p99.9 RTT (µs) | Maximum RTT (µs) |
|---:|---:|---:|---:|---:|---:|
| Idle | 50,000 | 36.0 | 58.9 | 89.7 | 137.5 |
| 25% | 50,000 | 32.0 | 75.0 | 103.1 | 226.7 |
| 50% | 50,000 | 32.0 | 104.0 | 161.1 | 2,637.8 |
| 100% | 50,000 | 26.7 | 107.0 | 439.4 | 1,097.2 |

The corresponding `summary.csv` files preserve per-repeat statistics, while the `rtt_*_all.csv` files contain pooled samples. `latency_by_load.png` provides the saved visualisation for each register-count condition.

### Interpretation cautions

- The median does not increase monotonically with the configured worker level. Tail metrics (p99 and p99.9) and maxima show more variability under load in these runs.
- The largest observed maximum is a tail event; it should not be treated as a stable or typical latency.
- These measurements include Python client overhead, simulator processing, and local operating-system scheduling. Since both endpoints run on the same host, there is no physical network path, PLC firmware, or PLC scan-cycle contribution.
- Do not generalise these loopback values to industrial deployments.

## UDP echo prototype

`udp_echo_server.py` and `udp_rtt_client.py` provide a minimal UDP echo round-trip test with a 4-byte sequence number. This is a starting point for experimentation, **not yet a designed or validated PC-to-PLC protocol**. It does not implement PLC register semantics, authentication, congestion control, application-level reliability, or a safety mechanism.

Run in separate terminals:

```bash
# Terminal 1
python3 udp_echo_server.py

# Terminal 2
python3 udp_rtt_client.py 127.0.0.1 9000 10000
```

The current UDP server binds to `127.0.0.1`; edit `HOST` in the script if you intentionally need to test across a trusted local network.

## Limitations

1. Modbus results use a simulator, not a physical PLC or OpenPLC deployment.
2. Client and server communicate over loopback; no Ethernet switch, cable, router, or network congestion is involved.
3. Client, simulator, and CPU load generator share one computer.
4. CPU load levels are configured worker counts, not independently verified CPU utilisation.
5. The experiment uses sequential request-response traffic and does not measure concurrent clients or sustained process-data throughput.
6. Five repeats are useful for an initial study but are not sufficient to establish hard real-time guarantees.
7. The UDP echo prototype is not yet a fair apples-to-apples comparison with Modbus TCP.

## Planned research extensions

- Repeat the baseline with a physical PLC or a clearly documented OpenPLC setup over Ethernet.
- Record hardware, OS version, Python version, network topology, PLC scan time, and test configuration with every run.
- Add controlled network delay, packet loss, and bandwidth contention.
- Compare equivalent application payloads and request rates across Modbus TCP and UDP.
- Design and document protocol framing, sequence handling, timeout behaviour, loss detection, and any required retransmission.
- Report repeated-run distributions and confidence intervals; avoid relying on a single maximum.
- Consider Linux scheduling and real-time configurations only after establishing a reproducible hardware/network baseline.

## Citation and reuse

If you use or build on this code, please cite the repository and preserve the MIT copyright and license notice. The results are preliminary simulator/loopback measurements and should be described as such.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
