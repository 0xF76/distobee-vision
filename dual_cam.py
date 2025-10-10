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


class DualSwitchableUDP:
    """Two independent pipelines, each switchable to any camera device."""

    def __init__(self, devices, host, base_port):
        self.devices = devices
        self.host = host
        self.base_port = base_port
        self.pipelines = [None, None]
        self.active_idx = [None, None]
        print(f"✅ Found {len(devices)} devices. Initializing two switchable feeds...")
        self.start_pipeline(0, None)
        self.start_pipeline(1, None)

    def build_pipeline(self, dev, port):
        """Build GStreamer pipeline for test pattern or camera."""
        if dev is None:
            print(f"▶️ Feed on port {port}: test pattern")
            launch = (
                f"videotestsrc is-live=true ! "
                f"videoconvert ! x264enc tune=zerolatency speed-preset=superfast bitrate=1000 key-int-max=30 ! "
                f"rtph264pay pt=96 ! udpsink host={self.host} port={port}"
            )
        else:
            print(f"▶️ Feed on port {port}: {dev}")
            launch = (
                f"v4l2src device={dev} ! "
                f"videoconvert ! videoscale ! videorate ! "
                f"video/x-raw,width=640,height=480,framerate=30/1 ! "
                f"x264enc tune=zerolatency speed-preset=superfast bitrate=2000 key-int-max=30 ! "
                f"rtph264pay pt=96 ! udpsink host={self.host} port={port}"
            )
        return Gst.parse_launch(launch)

    def start_pipeline(self, feed, dev):
        """Start (or restart) one feed's pipeline."""
        port = self.base_port + feed
        if self.pipelines[feed]:
            self.pipelines[feed].set_state(Gst.State.NULL)
        self.pipelines[feed] = self.build_pipeline(dev, port)
        self.pipelines[feed].set_state(Gst.State.PLAYING)

    def switch(self, feed, cam_idx):
        """Switch specific feed to a given camera index."""
        if not (0 <= feed <= 1):
            return "ERR invalid feed index (0 or 1)\n"
        if not (0 <= cam_idx < len(self.devices)):
            return "ERR invalid camera index\n"

        self.active_idx[feed] = cam_idx
        dev = self.devices[cam_idx]
        self.start_pipeline(feed, dev)
        return f"OK feed {feed} switched to {dev}\n"

    def test(self, feed):
        """Switch feed to test pattern."""
        if not (0 <= feed <= 1):
            return "ERR invalid feed index (0 or 1)\n"

        self.active_idx[feed] = None
        self.start_pipeline(feed, None)
        return f"OK feed {feed} switched to test pattern\n"

    def status(self):
        """Return current status of both feeds."""
        lines = ["STATUS:"]
        for i in range(2):
            port = self.base_port + i
            if self.active_idx[i] is None:
                lines.append(f"  Feed {i} → {self.host}:{port} (test pattern)")
            else:
                lines.append(f"  Feed {i} → {self.host}:{port} ({self.devices[self.active_idx[i]]})")
        return "\n".join(lines) + "\n"

    def stop_all(self):
        """Stop both pipelines."""
        for i in range(2):
            if self.pipelines[i]:
                self.pipelines[i].set_state(Gst.State.NULL)
        self.pipelines = [None, None]


def control_server(streamer, port=9000):
    """Simple TCP control interface."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(1)
    print(f"✅ Control server listening on TCP port {port}")

    while True:
        conn, addr = sock.accept()
        print(f"🔌 Client connected: {addr}")
        with conn:
            conn.sendall(b"Welcome to DualSwitchableUDP Control\n"
                         b"Commands:\n"
                         b"  STATUS\n"
                         b"  SWITCH <feed> <camera>\n"
                         b"  TEST <feed>\n"
                         b"  QUIT\n")
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                cmd = data.decode().strip().split()
                if not cmd:
                    continue

                if cmd[0].upper() == "STATUS":
                    conn.sendall(streamer.status().encode())
                elif cmd[0].upper() == "SWITCH" and len(cmd) == 3 and cmd[1].isdigit() and cmd[2].isdigit():
                    feed, cam = int(cmd[1]), int(cmd[2])
                    conn.sendall(streamer.switch(feed, cam).encode())
                elif cmd[0].upper() == "TEST" and len(cmd) == 2 and cmd[1].isdigit():
                    feed = int(cmd[1])
                    conn.sendall(streamer.test(feed).encode())
                elif cmd[0].upper() == "QUIT":
                    conn.sendall(b"Bye\n")
                    break
                else:
                    conn.sendall(b"ERR unknown command or wrong usage\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dual Switchable UDP Streamer with TCP Control")
    parser.add_argument("--host", default="127.0.0.1", help="Destination host")
    parser.add_argument("--port", type=int, default=5000, help="Base UDP port (e.g., 5000 and 5001)")
    parser.add_argument("--ctrl", type=int, default=9000, help="TCP control port")
    args = parser.parse_args()

    devices = find_av_devices()
    if len(devices) < 2:
        print("❌ Need at least two 'AV TO USB2.0' devices")
        sys.exit(1)

    print("✅ Detected cameras:")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d}")

    streamer = DualSwitchableUDP(devices, args.host, args.port)

    # Run TCP server in background
    server_thread = threading.Thread(target=control_server, args=(streamer, args.ctrl), daemon=True)
    server_thread.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("⏹️ Shutting down...")
        streamer.stop_all()
