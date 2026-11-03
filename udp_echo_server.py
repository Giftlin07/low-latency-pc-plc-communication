"""Minimal UDP echo server: sends back every packet it receives, unchanged."""
import socket

HOST = "127.0.0.1"   # use "0.0.0.0" to accept packets from other machines
PORT = 9000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # SOCK_DGRAM = UDP
sock.bind((HOST, PORT))
print(f"Echo server listening on {HOST}:{PORT}")

while True:
    data, addr = sock.recvfrom(2048)   # wait for a packet
    sock.sendto(data, addr)            # send the same bytes straight back
