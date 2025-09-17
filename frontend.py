#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import socket, threading, argparse, time

app = Flask(__name__)

class ScreenerClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.lock = threading.Lock()
        self._connect()

    def _connect(self):
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((self.ip, self.port))
                s.recv(1024)  # Welcome message
                self.sock = s
                print(f"✅ Connected to screener at {self.ip}:{self.port}")
                return
            except Exception as e:
                print(f"❌ Connection failed: {e}, retrying...")
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None
                time.sleep(2)

    def send(self, cmd):
        with self.lock:
            if not self.sock:
                self._connect()
            try:
                self.sock.sendall((cmd + "\n").encode())
                return self.sock.recv(1024).decode().strip()
            except Exception as e:
                print(f"❌ Communication error: {e}, reconnecting...")
                self._connect()
                try:
                    self.sock.sendall((cmd + "\n").encode())
                    return self.sock.recv(1024).decode().strip()
                except Exception as e2:
                    return f"ERR failed after reconnect: {e2}"



@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status")
def status():
    return jsonify(status=screener.send("STATUS"))

@app.route("/switch/<int:idx>", methods=["POST"])
def switch(idx):
    return jsonify(result=screener.send(f"SWITCH {idx}"))

@app.route("/test", methods=["POST"])
def test():
    return jsonify(result=screener.send("TEST"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Screener Camera Switcher Web Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Screener host (default: localhost)")
    parser.add_argument("--port", type=int, default=9000, help="Screener control port (default: 9000)")
    args = parser.parse_args()
    screener = ScreenerClient(args.host, args.port)
    app.run(host="0.0.0.0", port=8080)
