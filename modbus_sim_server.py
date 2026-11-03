"""Tiny Modbus TCP simulator (for testing the measurement script without a PLC).

Answers Modbus function 3 (Read Holding Registers) and 6 (Write Single
Register) with dummy data. It is deliberately simple. Use OpenPLC or a real
PLC for real results.

Usage:  python modbus_sim_server.py [host] [port]
"""
import socket
import struct
import sys
import threading

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5020   # 502 needs admin rights
registers = [i for i in range(1000)]


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def handle(conn):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    with conn:
        while True:
            header = recv_exact(conn, 7)          # MBAP header
            if header is None:
                return
            tid, pid, length, unit = struct.unpack("!HHHB", header)
            pdu = recv_exact(conn, length - 1)
            if pdu is None:
                return
            func = pdu[0]
            if func == 3:                          # read holding registers
                start, count = struct.unpack("!HH", pdu[1:5])
                vals = registers[start:start + count]
                body = bytes([3, len(vals) * 2]) + b"".join(struct.pack("!H", v) for v in vals)
            elif func == 6:                        # write single register
                addr, val = struct.unpack("!HH", pdu[1:5])
                registers[addr] = val
                body = pdu[:5]
            else:                                  # exception: illegal function
                body = bytes([func | 0x80, 1])
            conn.sendall(struct.pack("!HHHB", tid, 0, len(body) + 1, unit) + body)


srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((HOST, PORT))
srv.listen()
print(f"Modbus simulator listening on {HOST}:{PORT}")
while True:
    c, _ = srv.accept()
    threading.Thread(target=handle, args=(c,), daemon=True).start()
