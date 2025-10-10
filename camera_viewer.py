#!/usr/bin/env python3
import subprocess
import signal
import sys
import argparse

# GStreamer pipeline template for receiving an H.264 RTP stream over UDP
PIPE_TEMPLATE = (
    "gst-launch-1.0 udpsrc port={port} "
    "caps=\"application/x-rtp,media=video,encoding-name=H264,payload=96\" ! "
    "rtph264depay ! avdec_h264 ! videoconvert ! autovideosink sync=false"
)


def main():
    parser = argparse.ArgumentParser(description="Base Station Viewer for Multiple UDP Streams")
    parser.add_argument("--base-port", type=int, default=5000,
                        help="Base UDP port (e.g., 5000 → 5001, 5002, ...)")
    parser.add_argument("--feeds", type=int, default=2,
                        help="Number of camera feeds to open")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Receiver host (usually base station IP)")
    args = parser.parse_args()

    processes = []

    print("🎥 Starting Base Station Viewer")
    print(f"➡️  Listening for {args.feeds} feeds starting at UDP port {args.base_port}")

    try:
        for i in range(args.feeds):
            port = args.base_port + i
            cmd = PIPE_TEMPLATE.format(port=port)
            print(f"  ▶️ Launching feed {i} on port {port}")
            proc = subprocess.Popen(cmd, shell=True)
            processes.append(proc)

        print("\n✅ All viewers started. Press Ctrl+C to stop.")
        signal.pause()

    except KeyboardInterrupt:
        print("\n⏹️ Stopping all viewers...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait()
        print("✅ All viewers closed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
