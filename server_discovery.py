import socket
import sys
import argparse
import json
import time
import subprocess
import os
import logging
from datetime import datetime

class ServerDiscovery:
    """
    Server Discovery and Connection Check Tool.
    
    This class provides methods to discover APServers in the network and check connections.
    Can be used programmatically or via command line.
    """
    
    def __init__(self, default_port=65432, discovery_port=65433, setup_logging=True, logger=None):
        """
        Initialize the ServerDiscovery.
        
        Args:
            default_port (int): Default APServer port
            discovery_port (int): Discovery broadcast port
            setup_logging (bool): Whether to setup logging automatically
            logger (logging.Logger): Use external logger instead of creating own
        """
        self.default_port = default_port
        self.discovery_port = discovery_port
        
        # Setup logging - flexibel je nach Verwendung
        if logger:
            # Verwende übergebenen Logger
            self.logger = logger
        elif setup_logging:
            # Setup eigenes Logging (für CLI-Verwendung)
            self._setup_logging()
        else:
            # Verwende Standard Python Logger (für Import in anderen Scripts)
            self.logger = logging.getLogger("ServerDiscovery")

    def _setup_logging(self):
        """Setup logging configuration - nur für CLI-Verwendung."""
        # Prüfen ob bereits konfiguriert
        if logging.getLogger().handlers:
            # Logging bereits konfiguriert - verwende bestehende Konfiguration
            self.logger = logging.getLogger("ServerDiscovery")
            return
            
        # Create logs directory
        log_dir = "logs/discovery"
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate log filename with current date
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = f"{log_dir}/server_discovery_log_{today}.log"
        
        # Configure logging nur wenn noch nicht konfiguriert
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            handlers=[
                logging.FileHandler(log_filename, encoding="utf-8"),
            ]
        )
        
        self.logger = logging.getLogger("ServerDiscovery")
        self.logger.info("ServerDiscovery initialized - port: %d, discovery_port: %d", 
                        self.default_port, self.discovery_port)

    def check_server_connection(self, host, port=None, timeout=2):
        """
        Check if server is reachable at given host:port.
        
        Args:
            host (str): Server IP address
            port (int): Server port (uses default_port if None)
            timeout (int): Connection timeout in seconds
            
        Returns:
            bool: True if server is reachable
        """
        if port is None:
            port = self.default_port
            
        self.logger.debug("Checking connection to %s:%d (timeout: %ds)", host, port, timeout)
        
        try:
            with socket.create_connection((host, port), timeout=timeout):
                self.logger.info("Connection successful to %s:%d", host, port)
                return True
        except Exception as e:
            self.logger.debug("Connection failed to %s:%d - %s", host, port, str(e))
            return False

    def has_any_server(self, timeout=2):
        """
        Quick check if any server is available via discovery.
        Optimized for speed - returns as soon as first server is found.
        
        Args:
            timeout (int): Maximum time to wait for any server
            
        Returns:
            bool: True if at least one server is found
        """
        self.logger.debug("Starting discovery check (timeout: %ds)", timeout)
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('', self.discovery_port))
                sock.settimeout(0.2)
                
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    try:
                        data, addr = sock.recvfrom(1024)
                        server_info = json.loads(data.decode('utf-8'))
                        
                        if server_info.get("service") == "APServer":
                            self.logger.info("Server discovered via broadcast from %s: %s", 
                                           addr[0], server_info)
                            return True
                        
                    except (socket.timeout, json.JSONDecodeError, Exception) as e:
                        continue
                        
        except Exception as e:
            self.logger.error("Discovery error: %s", str(e))
        
        self.logger.debug("No server found via discovery after %ds", timeout)
        return False

    def find_server_ip(self, target_ip=None, target_port=None, discovery_timeout=5):
        """
        Find an APServer and return its IP address.
        
        Args:
            target_ip (str): Specific IP to check first (optional)
            target_port (int): Server port to use (uses default_port if None)
            discovery_timeout (int): How long to search via discovery
            
        Returns:
            str or None: IP address of found server or None if not found
        """
        if target_port is None:
            target_port = self.default_port
            
        self.logger.info("Finding server - target_ip: %s, port: %d, discovery_timeout: %ds", 
                        target_ip or "None", target_port, discovery_timeout)
        
        # 1. Wenn spezifische IP angegeben, diese zuerst prüfen
        if target_ip and self.check_server_connection(target_ip, target_port):
            self.logger.info("Server found at specified IP: %s:%d", target_ip, target_port)
            return target_ip
        
        # 2. Discovery verwenden
        self.logger.debug("Specific IP not reachable, trying discovery...")
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('', self.discovery_port))
                sock.settimeout(0.5)
                
                start_time = time.time()
                
                while time.time() - start_time < discovery_timeout:
                    try:
                        data, addr = sock.recvfrom(1024)
                        server_info = json.loads(data.decode('utf-8'))
                        
                        if server_info.get("service") == "APServer":
                            discovered_ip = server_info.get("ip")
                            discovered_port = server_info.get("port")
                            
                            # Discovered server testen
                            if discovered_ip and self.check_server_connection(discovered_ip, discovered_port):
                                self.logger.info("Server found via discovery: %s:%d", 
                                               discovered_ip, discovered_port)
                                return discovered_ip
                        
                    except (socket.timeout, json.JSONDecodeError, Exception):
                        continue
                        
        except Exception as e:
            self.logger.error("Discovery error during server search: %s", str(e))
        
        self.logger.warning("No server found after %ds discovery timeout", discovery_timeout)
        return None

    def start_server(self, server_script_path="ap_server.py", startup_timeout=10, target_ip=None):
        """
        Start APServer if not already running.
        
        Args:
            server_script_path (str): Path to server script
            startup_timeout (int): Time to wait for server startup
            target_ip (str): Specific IP to check for existing server
            
        Returns:
            bool: True if server started successfully and is reachable
        """
        self.logger.info("Attempting to start server - script: %s, timeout: %ds, target_ip: %s", 
                        server_script_path, startup_timeout, target_ip or "None")
        
        # Check if server is already running
        # 1. Erst spezifische IP prüfen (falls angegeben)
        if target_ip and self.check_server_connection(target_ip, self.default_port, timeout=2):
            self.logger.info("Server already running at specified IP: %s", target_ip)
            return True

        # 2. Dann Discovery prüfen
        if self.has_any_server(timeout=1):
            self.logger.info("Server already running (found via discovery)")
            return True
        
        try:
            # Check if server script exists
            if not os.path.isfile(server_script_path):
                self.logger.error("Server script not found: %s", server_script_path)
                return False
            
            self.logger.info("Starting server process: %s", server_script_path)
            
            # Start server process
            process = subprocess.Popen(
                [sys.executable, server_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # Wait for server to start up
            start_time = time.time()
            while time.time() - start_time < startup_timeout:
                # Check both specific IP and discovery
                server_running = False
                if target_ip:
                    server_running = self.check_server_connection(target_ip, self.default_port, timeout=1)
                if not server_running:
                    server_running = self.has_any_server(timeout=1)
                
                if server_running:
                    self.logger.info("Server started successfully in %.1fs", 
                                   time.time() - start_time)
                    return True
                time.sleep(0.5)

            # Server didn't start in time - cleanup
            self.logger.warning("Server did not start within %ds timeout", startup_timeout)
            try:
                process.terminate()
                self.logger.debug("Terminated server process")
            except Exception as e:
                self.logger.error("Error terminating server process: %s", str(e))
            
            return False

        except Exception as e:
            self.logger.error("Error starting server: %s", str(e))
            return False

def main():
    parser = argparse.ArgumentParser(
        description="APServer Discovery and Connection Check Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check if ANY server is available
  python server_discovery.py --check
  
  # Check specific server first, then discovery fallback
  python server_discovery.py --check --ip 192.168.1.100
  
  # Find server and return IP address
  python server_discovery.py --find
  
  # Find specific server with discovery fallback
  python server_discovery.py --find --ip 192.168.1.100
  
  # Start server if not running, then find IP
  python server_discovery.py --find --start-server
        """
    )
    
    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--check", action="store_true",
                           help="Check if server is available (Server available/No Server available)")
    mode_group.add_argument("--find", action="store_true",
                           help="Find server and return IP address")
    
    # Connection parameters
    parser.add_argument("--ip", "--host", dest="target_ip", 
                       help="Specific server IP address")
    parser.add_argument("--port", type=int, default=65432,
                       help="Server port (default: 65432)")
    parser.add_argument("--no-discovery", action="store_true",
                       help="Disable discovery fallback")
    parser.add_argument("--timeout", type=int, default=2,
                       help="Timeout in seconds (default: 2 for --check, 5 for --find)")
    
    # Server management
    parser.add_argument("--start-server", action="store_true",
                       help="Start server if not running")
    parser.add_argument("--server-script", default="ap_server.py",
                       help="Path to server script (default: ap_server.py)")
    
    # Logging options
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging to console")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Create discovery instance
    # Hier setup_logging=True (Default für CLI)
    discovery = ServerDiscovery(default_port=args.port)
    
    # Adjust logging level if requested
    if args.debug:
        discovery.logger.setLevel(logging.DEBUG)
    
    # Add console handler if verbose
    if args.verbose:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        discovery.logger.addHandler(console_handler)
    
    discovery.logger.info("=== ServerDiscovery started - Mode: %s, Target IP: %s ===", 
                         "check" if args.check else "find", args.target_ip or "None")
    
    # Auto-start server if requested
    if args.start_server:
        if not discovery.start_server(args.server_script, target_ip=args.target_ip):
            discovery.logger.error("Failed to start server")
            print("No Server available")
            sys.exit(1)
    
    # MODE 1: Check if server(s) are available
    if args.check:
        # Determine timeout
        check_timeout = args.timeout if args.timeout != 2 else 2
        
        if args.target_ip:
            # Check specific server first
            if discovery.check_server_connection(args.target_ip, args.port, timeout=2):
                discovery.logger.info("Check result: Server available at %s:%d", 
                                     args.target_ip, args.port)
                print("Server available")
                sys.exit(0)
            
            # Discovery fallback (if not disabled)
            if not args.no_discovery and discovery.has_any_server(timeout=check_timeout):
                discovery.logger.info("Check result: Server available via discovery")
                print("Server available")
                sys.exit(0)
            
            discovery.logger.info("Check result: No server available")
            print("No Server available")
            sys.exit(1)
        else:
            # Only discovery
            if discovery.has_any_server(timeout=check_timeout):
                discovery.logger.info("Check result: Server available via discovery")
                print("Server available")
                sys.exit(0)
            else:
                discovery.logger.info("Check result: No server available")
                print("No Server available")
                sys.exit(1)
    
    # MODE 2: Find server (get IP)
    elif args.find:
        # Determine timeout
        find_timeout = args.timeout if args.timeout != 2 else 5
        
        if args.no_discovery:
            # Only check specific IP
            if not args.target_ip:
                discovery.logger.error("--no-discovery requires --ip parameter")
                print("Error: --no-discovery requires --ip parameter", file=sys.stderr)
                sys.exit(1)
            
            if discovery.check_server_connection(args.target_ip, args.port):
                discovery.logger.info("Find result: Server found at %s", args.target_ip)
                print(args.target_ip)
                sys.exit(0)
            else:
                discovery.logger.warning("Find result: No server found at %s", args.target_ip)
                print("Warning: No server found", file=sys.stderr)
                sys.exit(1)
        else:
            # Find server with discovery
            found_ip = discovery.find_server_ip(
                target_ip=args.target_ip,
                target_port=args.port,
                discovery_timeout=find_timeout
            )
            
            if found_ip:
                discovery.logger.info("Find result: Server found at %s", found_ip)
                print(found_ip)
                sys.exit(0)
            else:
                discovery.logger.warning("Find result: No server found")
                print("Warning: No server found", file=sys.stderr)
                sys.exit(1)

if __name__ == "__main__":
    main()
