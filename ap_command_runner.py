from ap_command_server import CommandServer
from ap_logger import Logger
import queue

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Command Server with optional UI.")
    parser.add_argument("--use-ui", action="store_true", help="Enable the user interface.")
    args = parser.parse_args()

    # Erstelle die Queue
    log_queue = queue.Queue()

    # Initialisiere den Logger mit der Queue
    logger = Logger(log_queue=log_queue, use_ui=args.use_ui)
    logger.start()  # Starte den Logger-Thread

    # Initialisiere den Server mit der Queue
    server = CommandServer(log_queue=log_queue)
    server.start()

    # Starte die UI, falls aktiviert
    if args.use_ui:
        logger.start_ui()
    else:
        # Blockiere den Hauptthread, wenn keine GUI verwendet wird
        try:
            while True:
                pass  # Hauptthread bleibt aktiv
        except KeyboardInterrupt:
            print("Server stopped.")