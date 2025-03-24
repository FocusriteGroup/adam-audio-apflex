import socket
import json
import time
import sys

def send_command(command):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.connect(("127.0.0.1", 65432))
        client.send(json.dumps(command).encode("utf-8"))
        response = client.recv(1024).decode("utf-8")
        print(f"Response: {response}")
        return response

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug.py <averages>")
        sys.exit(1)

    try:
        averages = int(sys.argv[1])
    except ValueError:
        print("Error: Averages must be an integer.")
        sys.exit(1)

    # Send set_averages command
    send_command({"action": "set_averages", "averages": averages})

    # Periodically check status
    while True:
        status = send_command({"action": "get_status"})
        print(f"Status: {status}")
        if status == "complete":
            print("Operation complete.")
            break
        elif status == "error":
            print("Operation failed.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()