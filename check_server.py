import socket
import sys

def check_server(host="127.0.0.1", port=65432):
    """Check if the server is open and accepting connections."""
    try:

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(5)  # Set a timeout for the connection attempt
            client.connect((host, port))
            print(f"Server is open and accepting connections.")
    except socket.timeout:
        print(f"Connection to {host}:{port} timed out. The server might be down.")
    except ConnectionRefusedError:
        print(f"Connection to {host}:{port} was refused. The server might not be running.")
    except Exception as e:
        print(f"An error occurred while checking the server: {e}")
        sys.exit(1)  

if __name__ == "__main__":

    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 65432

    check_server(host, port)
    