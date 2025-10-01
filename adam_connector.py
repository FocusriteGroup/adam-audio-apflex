import socket
import sys
import argparse
import json
import time
import subprocess
import os
import logging
from datetime import datetime

class AdamConnector:
    """
    ADAM Audio Service Connector and Discovery Tool.
    
    This class provides methods to discover ADAM Audio services in the network 
    and check connections. Can be used programmatically or via command line.
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
        self.default_port = default_port
        self.discovery_port = discovery_port
        self.service_name = service_name
        
        # Setup logging - flexibel je nach Verwendung
        if logger:
            # Verwende übergebenen Logger
            self.logger = logger
        elif setup_logging:
            # Setup eigenes Logging (für CLI-Verwendung)
            self._setup_logging()
        else:
            # Verwende Standard Python Logger (für Import in anderen Scripts)
            self.logger = logging.getLogger("AdamConnector")

    def _setup_logging(self):
        """Setup logging configuration - nur für CLI-Verwendung."""
        # Prüfen ob bereits konfiguriert
        if logging.getLogger().handlers:
            # Logging bereits konfiguriert - verwende bestehende Konfiguration
            self.logger = logging.getLogger("AdamConnector")
            return
            
        # Create logs directory für ADAM Audio
        log_dir = "logs/adam_audio"
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate log filename with current date
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = f"{log_dir}/adam_connector_log_{today}.log"
        
        # Configure logging nur wenn noch nicht konfiguriert
        # NUR File-Handler - KEIN Console-Handler!
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            handlers=[
                logging.FileHandler(log_filename, encoding="utf-8"),
                # ENTFERNT: logging.StreamHandler()
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
        if port is None:
            port = self.default_port
            
        self.logger.debug("Checking connection to ADAM service %s:%d (timeout: %ds)", host, port, timeout)
        
        try:
            with socket.create_connection((host, port), timeout=timeout):
                self.logger.info("Connection successful to ADAM service %s:%d", host, port)
                return True
        except Exception as e:
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
        self.logger.debug("Starting ADAM service discovery check (timeout: %ds)", timeout)
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('', self.discovery_port))
                sock.settimeout(0.2)
                
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    try:
                        data, addr = sock.recvfrom(1024)
                        service_info = json.loads(data.decode('utf-8'))
                        
                        # Check for ADAM Audio services only
                        service_type = service_info.get("service", "")
                        company = service_info.get("company", "")
                        
                        if (service_type == self.service_name or 
                            company == "ADAM Audio"):
                            self.logger.info("ADAM service discovered via broadcast from %s: %s", 
                                           addr[0], service_info)
                            return True
                        
                    except (socket.timeout, json.JSONDecodeError, Exception) as e:
                        continue
                        
        except Exception as e:
            self.logger.error("Discovery error: %s", str(e))
        
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
        
        # 1. Wenn spezifische IP angegeben, diese zuerst prüfen
        if target_ip and self.check_service_connection(target_ip, target_port):
            self.logger.info("ADAM service found at specified IP: %s:%d", target_ip, target_port)
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
                        
                    except (socket.timeout, json.JSONDecodeError, Exception):
                        continue
                        
        except Exception as e:
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
            
            # Plattform-spezifische Subprocess-Konfiguration
            if os.name == 'nt':  # Windows
                process = subprocess.Popen(
                    [sys.executable, service_script_path, "--service-name", self.service_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:  # macOS/Linux
                process = subprocess.Popen(
                    [sys.executable, service_script_path, "--service-name", self.service_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True  # Unix-equivalent zu CREATE_NEW_PROCESS_GROUP
                )
            
            # Wait for service to start up
            start_time = time.time()
            while time.time() - start_time < startup_timeout:
                # Check both specific IP and discovery
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

            # Service didn't start in time - cleanup
            self.logger.warning("ADAM service did not start within %ds timeout", startup_timeout)
            try:
                if os.name == 'nt':  # Windows
                    process.terminate()
                else:  # macOS/Linux
                    process.terminate()
                    # Zusätzlicher Kill nach kurzer Zeit falls nötig
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                self.logger.debug("Terminated ADAM service process")
            except Exception as e:
                self.logger.error("Error terminating ADAM service process: %s", str(e))
            
            return False

        except Exception as e:
            self.logger.error("Error starting ADAM service: %s", str(e))
            return False

def main():
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
    
    # Create connector instance für ADAM Audio
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
