#!/usr/bin/env python3
import gi, sys, argparse, threading, socket
gi.require_version("Gst", "1.0")
from gi.repository import Gst

Gst.init(None)

def find_av_devices():
    """Find all 'AV TO USB2.0' devices."""
    monitor = Gst.DeviceMonitor()
    monitor.add_filter("Video/Source", None)
    monitor.start()
    devices = []
    for dev in monitor.get_devices():
        name = dev.get_display_name()
        props = dev.get_properties()
        if "AV TO USB2.0" in name and props.has_field("device.path"):
            devices.append(props.get_string("device.path"))
    monitor.stop()
    return devices

class SwitchableUDP:
    def __init__(self, devices, host, port):
        self.devices = devices
        self.host = host
        self.port = port
        self.pipeline = None
        self.active_idx = None
        # Start with test pattern
        self.start_pipeline(None)

    def build_pipeline(self, dev):
        if dev is None:
            print(f"▶️ Streaming test pattern to {self.host}:{self.port}")
            launch = (
                f"videotestsrc is-live=true ! "
                f"videoconvert ! x264enc tune=zerolatency speed-preset=superfast bitrate=1000 key-int-max=30 ! "
                f"rtph264pay pt=96 ! udpsink host={self.host} port={self.port}"
            )
        else:
            print(f"▶️ Streaming camera {dev} to {self.host}:{self.port}")
            launch = (
                f"v4l2src device={dev} ! "
                f"videoconvert ! videoscale ! videorate ! "
                f"video/x-raw,width=640,height=480,framerate=30/1 ! "
                f"x264enc tune=zerolatency speed-preset=superfast bitrate=2000 key-int-max=30 ! "
                f"rtph264pay pt=96 ! udpsink host={self.host} port={self.port}"
            )
        return Gst.parse_launch(launch)

    def start_pipeline(self, dev):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        self.pipeline = self.build_pipeline(dev)
        self.pipeline.set_state(Gst.State.PLAYING)

    def switch(self, idx):
        if 0 <= idx < len(self.devices):
            self.active_idx = idx
            self.start_pipeline(self.devices[idx])
            return f"OK switched to {self.devices[idx]}\n"
        return "ERR invalid index\n"

    def status(self):
        if self.active_idx is None:
            return "STATUS test pattern\n"
        return f"STATUS {self.devices[self.active_idx]}\n"

    def test(self):
        self.active_idx = None
        self.start_pipeline(None)
        return "OK switched to test pattern\n"

    def stop(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

def control_server(udp, port=9000):
    """Simple TCP server to control the UDP streamer."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(1)
    print(f"✅ Control server listening on TCP port {port}")

    while True:
        conn, addr = sock.accept()
        print(f"🔌 Client connected: {addr}")
        with conn:
            conn.sendall(b"Welcome to SwitchableUDP Control\n")
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                cmd = data.decode().strip()
                if cmd.upper() == "STATUS":
                    conn.sendall(udp.status().encode())
                elif cmd.upper().startswith("SWITCH"):
                    parts = cmd.split()
                    if len(parts) == 2 and parts[1].isdigit():
                        resp = udp.switch(int(parts[1]))
                        conn.sendall(resp.encode())
                    else:
                        conn.sendall(b"ERR usage: SWITCH <index>\n")
                elif cmd.upper() == "TEST":
                    conn.sendall(udp.test().encode())
                elif cmd.upper() == "QUIT":
                    conn.sendall(b"Bye\n")
                    break
                else:
                    conn.sendall(b"ERR unknown command\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Switchable UDP Camera Streamer with TCP control")
    parser.add_argument("--host", default="127.0.0.1", help="Destination host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Destination UDP port (default: 5000)")
    parser.add_argument("--ctrl", type=int, default=9000, help="TCP control port (default: 9000)")
    args = parser.parse_args()

    devices = find_av_devices()
    if not devices:
        print("❌ No AV TO USB2.0 devices found")
        sys.exit(1)

    print("✅ Detected cameras:")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d}")

    udp = SwitchableUDP(devices, args.host, args.port)

    # Run TCP control in a thread
    server_thread = threading.Thread(target=control_server, args=(udp, args.ctrl), daemon=True)
    server_thread.start()

    try:
        # Keep main thread alive
        while True:
            pass
    except KeyboardInterrupt:
        print("⏹️ Shutting down...")
        udp.stop()
