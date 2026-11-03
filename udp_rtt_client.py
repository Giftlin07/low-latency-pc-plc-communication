"""UDP round-trip-time client.

Sends N small packets to the echo server, one at a time, and times each
round trip. Prints summary statistics and saves every sample to a CSV so
you can plot a latency histogram later.

Usage:  python udp_rtt_client.py [host] [port] [count]
"""
import csv
import socket
import statistics
import struct
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
COUNT = int(sys.argv[3]) if len(sys.argv) > 3 else 10000
TIMEOUT_S = 0.5

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(TIMEOUT_S)

rtts_us = []   # round-trip times in microseconds
lost = 0

for seq in range(COUNT):
    payload = struct.pack("!I", seq)           # 4-byte sequence number
    t0 = time.perf_counter_ns()                # high-resolution clock
    sock.sendto(payload, (HOST, PORT))
    try:
        reply, _ = sock.recvfrom(2048)
    except socket.timeout:
        lost += 1
        continue
    t1 = time.perf_counter_ns()

    if reply != payload:                       # stale reply from an earlier packet
        lost += 1
        continue
    rtts_us.append((t1 - t0) / 1000)

if not rtts_us:
    sys.exit("No replies received. Is the server running?")

rtts_sorted = sorted(rtts_us)
p99 = rtts_sorted[int(0.99 * len(rtts_sorted)) - 1]

print(f"Packets sent : {COUNT}")
print(f"Lost         : {lost}")
print(f"Min          : {min(rtts_us):9.1f} us")
print(f"Mean         : {statistics.mean(rtts_us):9.1f} us")
print(f"Median       : {statistics.median(rtts_us):9.1f} us")
print(f"99th pct     : {p99:9.1f} us")
print(f"Max          : {max(rtts_us):9.1f} us")
print(f"Jitter (std) : {statistics.pstdev(rtts_us):9.1f} us")

with open("rtt_samples.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rtt_us"])
    w.writerows([[round(x, 1)] for x in rtts_us])
print("Saved samples to rtt_samples.csv")
