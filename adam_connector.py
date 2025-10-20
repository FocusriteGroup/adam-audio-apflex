"""
adam_connector.py

ADAM Audio Service Connector and Discovery Tool
------------------------------------------------

Author: Thilo Rode
Company: ADAM Audio GmbH
Version: 0.1
Date: 2025-10-20

This module provides the AdamConnector class and a command-line interface for discovering,
connecting to, and managing ADAM Audio network services in a production environment.

Key Features:
- Discover ADAM Audio services on the local network using UDP broadcast
- Check if a specific service is reachable at a given IP and port
- Find the IP address of a service using discovery or direct connection
- Start the ADAM Audio service if it is not already running
- Provide a CLI for integration with scripts, automation, and diagnostics

Typical Usage:
- As a library: Import AdamConnector to programmatically manage service discovery and connections
- As a script: Run from the command line to check, find, or start ADAM Audio services

Example CLI commands:
    python adam_connector.py --check
    python adam_connector.py --find
    python adam_connector.py --find --start-service

This module is intended for use in ADAM Audio production line software, workstation clients,
and automated test environments where robust service discovery and management are required.
"""

# Standard library imports
import socket  # For network communication
import sys     # For system exit and interpreter info
import argparse  # For command-line argument parsing
import json    # For encoding/decoding service info
import time    # For timeouts and timestamps
import subprocess  # For starting service processes
import os      # For file and path operations
import logging # For logging events and errors
from datetime import datetime  # For log file naming


class AdamConnector:
    """
    ADAM Audio Service Connector and Discovery Tool.
    
    This class provides methods to:
    - Discover ADAM Audio services in the network via UDP broadcast
    - Check if a service is reachable at a given IP/port
    - Find a service IP using discovery or direct connection
    - Start the ADAM Audio service if not running
    Can be used programmatically or via command line.
    """

    def __init__(self, default_port=65432, discovery_port=65433, service_name="ADAMService", setup_logging=True, logger=None):
        """
        Initialize the ADAM Audio Connector.
        
        Args:
            default_port (int): Default ADAM service port
            discovery_port (int): Discovery broadcast port
            service_name (str): Name of service to discover (default: ADAMService)
            setup_logging (bool): Whether to setup logging automatically
            logger (logging.Logger): Use external logger instead of creating own
        """
        self.default_port = default_port  # Default TCP port for service
        self.discovery_port = discovery_port  # UDP port for service discovery
        self.service_name = service_name  # Service name to look for
        # Setup logging depending on context (CLI, import, or external logger)
        if logger:
            # Use externally provided logger
            self.logger = logger
        elif setup_logging:
            # Setup own logging (for CLI usage)
            self._setup_logging()
        else:
            # Use default Python logger (for import in other scripts)
            self.logger = logging.getLogger("AdamConnector")

    def _setup_logging(self):
        """
        Setup logging configuration for CLI usage.
        Creates a log file in logs/adam_audio with the current date.
        Only a file handler is used (no console output by default).
        """
        # Use existing logging config if present
        if logging.getLogger().handlers:
            self.logger = logging.getLogger("AdamConnector")
            return
        # Ensure log directory exists
        log_dir = "logs/adam_audio"
        os.makedirs(log_dir, exist_ok=True)
        # Log file name with date
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = f"{log_dir}/adam_connector_log_{today}.log"
        # Configure logging (file only)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            handlers=[
                logging.FileHandler(log_filename, encoding="utf-8"),
            ]
        )
        self.logger = logging.getLogger("AdamConnector")
        self.logger.info("ADAM Audio Connector initialized - service: %s, port: %d, discovery_port: %d",
                        self.service_name, self.default_port, self.discovery_port)

    def check_service_connection(self, host, port=None, timeout=2):
        """
        Check if ADAM Audio service is reachable at given host:port.
        
        Args:
            host (str): Service IP address
            port (int): Service port (uses default_port if None)
            timeout (int): Connection timeout in seconds
            
        Returns:
            bool: True if service is reachable
        """
        # Use default port if not specified
        if port is None:
            port = self.default_port

        # Log the connection attempt for debugging
        self.logger.debug("Checking connection to ADAM service %s:%d (timeout: %ds)", host, port, timeout)

        try:
            # Attempt to open a TCP connection to the service
            # This will raise an exception if the service is not reachable
            with socket.create_connection((host, port), timeout=timeout):
                # If connection succeeds, log and return True
                self.logger.info("Connection successful to ADAM service %s:%d", host, port)
                return True
        except (socket.error, socket.timeout) as e:
            # If connection fails, log the error and return False
            self.logger.debug("Connection failed to %s:%d - %s", host, port, str(e))
            return False

    def has_any_service(self, timeout=2):
        """
        Quick check if any ADAM Audio service is available via discovery.
        Optimized for speed - returns as soon as first service is found.
        
        Args:
            timeout (int): Maximum time to wait for any service
            
        Returns:
            bool: True if at least one ADAM service is found
        """
        # Log the start of the discovery process
        self.logger.debug("Starting ADAM service discovery check (timeout: %ds)", timeout)

        try:
            # Create a UDP socket for listening to service broadcasts
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # Bind to the discovery port on all interfaces (0.0.0.0)
                sock.bind(('', self.discovery_port))
                # Set a short timeout for non-blocking polling
                sock.settimeout(0.2)

                start_time = time.time()

                # Loop until the specified timeout expires
                while time.time() - start_time < timeout:
                    try:
                        # Wait for a UDP broadcast packet from any service
                        data, addr = sock.recvfrom(1024)
                        # Decode the received data as JSON
                        service_info = json.loads(data.decode('utf-8'))

                        # Extract service type and company from the broadcast
                        service_type = service_info.get("service", "")
                        company = service_info.get("company", "")

                        # If the broadcast matches the expected service, log and return True
                        if (service_type == self.service_name or
                            company == "ADAM Audio"):
                            self.logger.info("ADAM service discovered via broadcast from %s: %s",
                                           addr[0], service_info)
                            return True

                    except (socket.timeout, json.JSONDecodeError, OSError):
                        # Ignore timeouts and malformed packets, keep listening
                        continue

        except (socket.error, OSError) as e:
            # Log any socket errors encountered during discovery
            self.logger.error("Discovery error: %s", str(e))

        # If no service was found, log and return False
        self.logger.debug("No ADAM service found via discovery after %ds", timeout)
        return False

    def find_service_ip(self, target_ip=None, target_port=None, discovery_timeout=5):
        """
        Find an ADAM Audio service and return its IP address.
        
        Args:
            target_ip (str): Specific IP to check first (optional)
            target_port (int): Service port to use (uses default_port if None)
            discovery_timeout (int): How long to search via discovery
            
        Returns:
            str or None: IP address of found service or None if not found
        """
        if target_port is None:
            target_port = self.default_port

        self.logger.info("Finding ADAM service - target_ip: %s, port: %d, discovery_timeout: %ds",
                        target_ip or "None", target_port, discovery_timeout)

        # Step 1: If a specific IP is provided, check if a service is running there
        if target_ip and self.check_service_connection(target_ip, target_port):
            # If reachable, log and return the IP
            self.logger.info("ADAM service found at specified IP: %s:%d", target_ip, target_port)
            return target_ip

        # Step 2: If not found, use UDP discovery to search the network
        self.logger.debug("Specific IP not reachable, trying discovery...")

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('', self.discovery_port))
                sock.settimeout(0.5)

                start_time = time.time()

                while time.time() - start_time < discovery_timeout:
                    try:
                        data, addr = sock.recvfrom(1024)
                        service_info = json.loads(data.decode('utf-8'))

                        # Check for ADAM Audio services only
                        service_type = service_info.get("service", "")
                        company = service_info.get("company", "")

                        if (service_type == self.service_name or
                            company == "ADAM Audio"):
                            discovered_ip = service_info.get("ip")
                            discovered_port = service_info.get("port")

                            # Test discovered service
                            if discovered_ip and self.check_service_connection(discovered_ip, discovered_port):
                                self.logger.info("ADAM service found via discovery: %s:%d",
                                               discovered_ip, discovered_port)
                                return discovered_ip

                    except (socket.timeout, json.JSONDecodeError, OSError):
                        continue

        except (socket.error, json.JSONDecodeError, OSError) as e:
            self.logger.error("Discovery error during service search: %s", str(e))

        self.logger.warning("No ADAM service found after %ds discovery timeout", discovery_timeout)
        return None

    def start_service(self, service_script_path="adam_service.py", startup_timeout=10, target_ip=None):
        """
        Start ADAM Audio service if not already running.
        
        Args:
            service_script_path (str): Path to service script
            startup_timeout (int): Time to wait for service startup
            target_ip (str): Specific IP to check for existing service
            
        Returns:
            bool: True if service started successfully and is reachable
        """
        self.logger.info("Attempting to start ADAM service - script: %s, timeout: %ds, target_ip: %s",
                        service_script_path, startup_timeout, target_ip or "None")

        # Check if service is already running
        # 1. Erst spezifische IP prüfen (falls angegeben)
        if target_ip and self.check_service_connection(target_ip, self.default_port, timeout=2):
            self.logger.info("ADAM service already running at specified IP: %s", target_ip)
            return True

        # 2. Dann Discovery prüfen
        if self.has_any_service(timeout=1):
            self.logger.info("ADAM service already running (found via discovery)")
            return True

        try:
            # Check if service script exists
            if not os.path.isfile(service_script_path):
                self.logger.error("ADAM service script not found: %s", service_script_path)
                return False

            self.logger.info("Starting ADAM service process: %s", service_script_path)

            # Platform-specific subprocess configuration
            if os.name == 'nt':  # Windows
                # Start the service as a new process group on Windows
                process = subprocess.Popen(
                    [sys.executable, service_script_path, "--service-name", self.service_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:  # macOS/Linux
                # Start the service in a new session on Unix-like systems
                process = subprocess.Popen(
                    [sys.executable, service_script_path, "--service-name", self.service_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True  # Unix equivalent to CREATE_NEW_PROCESS_GROUP
                )

            # Wait for the service to start up, polling for availability
            start_time = time.time()
            while time.time() - start_time < startup_timeout:
                # Check both specific IP and discovery for service availability
                service_running = False
                if target_ip:
                    service_running = self.check_service_connection(target_ip, self.default_port, timeout=1)
                if not service_running:
                    service_running = self.has_any_service(timeout=1)

                if service_running:
                    self.logger.info("ADAM service started successfully in %.1fs",
                                   time.time() - start_time)
                    return True
                time.sleep(0.5)

            # If the service didn't start in time, terminate the process
            self.logger.warning("ADAM service did not start within %ds timeout", startup_timeout)
            try:
                if os.name == 'nt':  # Windows
                    process.terminate()
                else:  # macOS/Linux
                    process.terminate()
                    # Additional kill after short wait if needed
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                self.logger.debug("Terminated ADAM service process")
            except (subprocess.SubprocessError, OSError) as e:
                self.logger.error("Error terminating ADAM service process: %s", str(e))

            return False

        except (subprocess.SubprocessError, OSError) as e:
            # Log any errors encountered while starting the service
            self.logger.error("Error starting ADAM service: %s", str(e))
            return False

def main():
    """
    Main entry point for ADAM Audio Service Discovery and Connection Tool.
    Parses command-line arguments and executes requested actions.
    """
    parser = argparse.ArgumentParser(
        description="ADAM Audio Service Discovery and Connection Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        # Check if ANY ADAM service is available
        python adam_connector.py --check
        
        # Check specific service first, then discovery fallback
        python adam_connector.py --check --ip 192.168.1.100
        
        # Find ADAM service and return IP address
        python adam_connector.py --find
        
        # Find specific service with discovery fallback
        python adam_connector.py --find --ip 192.168.1.100
        
        # Start ADAM service if not running, then find IP
        python adam_connector.py --find --start-service
        
        # Connect to specific ADAM service type
        python adam_connector.py --find --service-name ADAMService
        """
    )

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--check", action="store_true",
                           help="Check if ADAM service is available (Service available/No Service available)")
    mode_group.add_argument("--find", action="store_true",
                           help="Find ADAM service and return IP address")

    # Connection parameters
    parser.add_argument("--ip", "--host", dest="target_ip",
                       help="Specific service IP address")
    parser.add_argument("--port", type=int, default=65432,
                       help="Service port (default: 65432)")
    parser.add_argument("--service-name", default="ADAMService",
                       help="Name of ADAM service to discover (default: ADAMService)")
    parser.add_argument("--no-discovery", action="store_true",
                       help="Disable discovery fallback")
    parser.add_argument("--timeout", type=int, default=2,
                       help="Timeout in seconds (default: 2 for --check, 5 for --find)")

    # Service management
    parser.add_argument("--start-service", action="store_true",
                       help="Start ADAM service if not running")
    parser.add_argument("--service-script", default="adam_service.py",
                       help="Path to ADAM service script (default: adam_service.py)")

    # Logging options
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging to console")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")

    args = parser.parse_args()

    # Create connector instance for ADAM Audio
    connector = AdamConnector(
        default_port=args.port,
        service_name=args.service_name
    )

    # Adjust logging level if requested
    if args.debug:
        connector.logger.setLevel(logging.DEBUG)
    # Add console handler if verbose
    if args.verbose:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        connector.logger.addHandler(console_handler)

    connector.logger.info("=== ADAM Audio Connector started - Mode: %s, Target IP: %s, Service: %s ===",
                         "check" if args.check else "find", args.target_ip or "None", args.service_name)

    # MODE 1: Check if ADAM service(s) are available
    if args.check:
        # Auto-start service if requested UND check mode
        if args.start_service:
            if not connector.start_service(args.service_script, target_ip=args.target_ip):
                connector.logger.error("Failed to start ADAM service")
                print("No ADAM Service available")
                sys.exit(1)

        # Determine timeout
        check_timeout = args.timeout if args.timeout != 2 else 2

        if args.target_ip:
            # Check specific service first
            if connector.check_service_connection(args.target_ip, args.port, timeout=2):
                connector.logger.info("Check result: ADAM service available at %s:%d",
                                     args.target_ip, args.port)
                print("ADAM Service available")
                sys.exit(0)

            # Discovery fallback (if not disabled)
            if not args.no_discovery and connector.has_any_service(timeout=check_timeout):
                connector.logger.info("Check result: ADAM service available via discovery")
                print("ADAM Service available")
                sys.exit(0)

            connector.logger.info("Check result: No ADAM service available")
            print("No ADAM Service available")
            sys.exit(1)
        else:
            # Only discovery
            if connector.has_any_service(timeout=check_timeout):
                connector.logger.info("Check result: ADAM service available via discovery")
                print("ADAM Service available")
                sys.exit(0)
            else:
                connector.logger.info("Check result: No ADAM service available")
                print("No ADAM Service available")
                sys.exit(1)

    # MODE 2: Find ADAM service (get IP)
    elif args.find:
        # Auto-start service if requested UND find mode
        if args.start_service:
            if not connector.start_service(args.service_script, target_ip=args.target_ip):
                connector.logger.error("Failed to start ADAM service")
                print("Warning: No ADAM service found", file=sys.stderr)
                sys.exit(1)

        # Determine timeout
        find_timeout = args.timeout if args.timeout != 2 else 5

        if args.no_discovery:
            # Only check specific IP
            if not args.target_ip:
                connector.logger.error("--no-discovery requires --ip parameter")
                print("Error: --no-discovery requires --ip parameter", file=sys.stderr)
                sys.exit(1)

            if connector.check_service_connection(args.target_ip, args.port):
                connector.logger.info("Find result: ADAM service found at %s", args.target_ip)
                print(args.target_ip)
                sys.exit(0)
            else:
                connector.logger.warning("Find result: No ADAM service found at %s", args.target_ip)
                print("Warning: No ADAM service found", file=sys.stderr)
                sys.exit(1)
        else:
            # Find service with discovery
            found_ip = connector.find_service_ip(
                target_ip=args.target_ip,
                target_port=args.port,
                discovery_timeout=find_timeout
            )

            if found_ip:
                connector.logger.info("Find result: ADAM service found at %s", found_ip)
                print(found_ip)
                sys.exit(0)
            else:
                connector.logger.warning("Find result: No ADAM service found")
                print("Warning: No ADAM service found", file=sys.stderr)
                sys.exit(1)

if __name__ == "__main__":
    main()
