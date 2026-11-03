"""Modbus TCP round-trip-time measurement, written at the byte level.

Sends N "Read Holding Registers" requests, one at a time over a single TCP
connection, and times each request-response. Saves every sample to a CSV.

Usage:
  python modbus_rtt.py [host] [port] [count] [registers] [label]

  host       default 127.0.0.1  (your OpenPLC / PLC IP)
  port       default 5020       (real Modbus devices use 502)
  count      default 10000      requests to send
  registers  default 10         registers read per request (payload size)
  label      default "run"      output file: rtt_<label>.csv
"""
import csv
import socket
import statistics
import struct
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5020
COUNT = int(sys.argv[3]) if len(sys.argv) > 3 else 10000
NREGS = int(sys.argv[4]) if len(sys.argv) > 4 else 10
LABEL = sys.argv[5] if len(sys.argv) > 5 else "run"
UNIT_ID = 1
WARMUP = 200   # discard the first requests (connection setup, cold caches)


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed by server")
        buf += chunk
    return buf


sock = socket.create_connection((HOST, PORT), timeout=1.0)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # don't batch small packets

rtts_us = []
errors = 0
for i in range(COUNT + WARMUP):
    tid = i & 0xFFFF
    # MBAP header (transaction id, protocol id=0, length=6, unit id) + PDU
    # PDU = function 3, start address 0, number of registers
    request = struct.pack("!HHHBBHH", tid, 0, 6, UNIT_ID, 3, 0, NREGS)

    t0 = time.perf_counter_ns()
    sock.sendall(request)
    try:
        header = recv_exact(sock, 7)
        rtid, _, length, _ = struct.unpack("!HHHB", header)
        pdu = recv_exact(sock, length - 1)
    except (socket.timeout, ConnectionError):
        errors += 1
        continue
    t1 = time.perf_counter_ns()

    if rtid != tid or pdu[0] != 3:       # wrong reply or Modbus exception
        errors += 1
        continue
    if i >= WARMUP:
        rtts_us.append((t1 - t0) / 1000)

if not rtts_us:
    sys.exit("No valid replies. Check host, port and that the server is running.")

s = sorted(rtts_us)
pct = lambda p: s[min(len(s) - 1, int(p / 100 * len(s)))]

print(f"Target       : {HOST}:{PORT}, {NREGS} registers/request")
print(f"Requests     : {len(rtts_us)} ok, {errors} errors")
print(f"Min          : {s[0]:9.1f} us")
print(f"Mean         : {statistics.mean(rtts_us):9.1f} us")
print(f"Median       : {statistics.median(rtts_us):9.1f} us")
print(f"99th pct     : {pct(99):9.1f} us")
print(f"99.9th pct   : {pct(99.9):9.1f} us")
print(f"Max          : {s[-1]:9.1f} us")
print(f"Jitter (std) : {statistics.pstdev(rtts_us):9.1f} us")

fname = f"rtt_{LABEL}.csv"
with open(fname, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rtt_us"])
    w.writerows([[round(x, 1)] for x in rtts_us])
print(f"Saved samples to {fname}")
