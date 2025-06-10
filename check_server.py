import socket
import sys
import subprocess
import time

def is_server_running(host="127.0.0.1", port=65432, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def start_server():
    # Startet den Server ap_server.py unabhängig vom Terminal und unterdrückt die Ausgaben
    subprocess.Popen(
        [sys.executable, "ap_server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP  # Windows equivalent to start_new_session
    )
    time.sleep(1)  # Kurzes Warten, damit der Server starten kann

def wait_for_server(host, port, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_server_running(host, port):
            return True
        time.sleep(0.5)
    return False

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 65432

    if is_server_running(host, port):
        print(f"Server is open and accepting connections.")
        sys.exit(0)

    start_server()
    if wait_for_server(host, port, timeout=10):
        print(f"Server is open and accepting connections.")
        sys.exit(0)
    else:
        print(f"Connection to {host}:{port} was refused. The server might not be running.")
        sys.exit(1)
