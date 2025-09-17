from flask import Flask, render_template, jsonify
import socket, threading

ROVER_IP = "127.0.0.1"   # <-- change this to your CM5 IP
ROVER_CTRL_PORT = 9000

app = Flask(__name__)

class RoverClient:
    def __init__(self, ip, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip, port))
        self.sock.settimeout(2)
        self.lock = threading.Lock()
        self.sock.recv(1024)  # discard welcome banner

    def send(self, cmd):
        with self.lock:
            self.sock.sendall((cmd + "\n").encode())
            return self.sock.recv(1024).decode().strip()

rover = RoverClient(ROVER_IP, ROVER_CTRL_PORT)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/status")
def status():
    return jsonify(status=rover.send("STATUS"))

@app.route("/switch/<int:idx>", methods=["POST"])
def switch(idx):
    return jsonify(result=rover.send(f"SWITCH {idx}"))

@app.route("/test", methods=["POST"])
def test():
    return jsonify(result=rover.send("TEST"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
