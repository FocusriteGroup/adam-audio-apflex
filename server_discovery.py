import socket
import sys
import argparse
import json
import time

class ServerDiscovery:
    """
    Server Discovery and Connection Check Tool.
    
    This class provides methods to discover APServers in the network and check connections.
    Can be used programmatically or via command line.
    """
    
    def __init__(self, default_port=65432, discovery_port=65433):
        """
        Initialize the ServerDiscovery.
        
        Args:
            default_port (int): Default APServer port
            discovery_port (int): Discovery broadcast port
        """
        self.default_port = default_port
        self.discovery_port = discovery_port

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
            
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
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
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('', self.discovery_port))
                sock.settimeout(0.2)  # Sehr kurzes Socket-Timeout
                
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    try:
                        data, addr = sock.recvfrom(1024)
                        server_info = json.loads(data.decode('utf-8'))
                        
                        if server_info.get("service") == "APServer":
                            return True  # Sofort beenden wenn erster Server gefunden
                        
                    except (socket.timeout, json.JSONDecodeError, Exception):
                        continue
                        
        except Exception:
            pass
        
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
            
        # 1. Wenn spezifische IP angegeben, diese zuerst prüfen
        if target_ip and self.check_server_connection(target_ip, target_port):
            return target_ip
        
        # 2. Discovery verwenden
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
                                return discovered_ip
                        
                    except (socket.timeout, json.JSONDecodeError, Exception):
                        continue
                        
        except Exception:
            pass
        
        return None

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
    
    args = parser.parse_args()
    
    # Create discovery instance
    discovery = ServerDiscovery(default_port=args.port)
    
    # MODE 1: Check if server(s) are available
    if args.check:
        # Determine timeout
        check_timeout = args.timeout if args.timeout != 2 else 2
        
        if args.target_ip:
            # Check specific server first
            if discovery.check_server_connection(args.target_ip, args.port, timeout=2):
                print("Server available")
                sys.exit(0)
            
            # Discovery fallback (if not disabled)
            if not args.no_discovery and discovery.has_any_server(timeout=check_timeout):
                print("Server available")
                sys.exit(0)
            
            print("No Server available")
            sys.exit(1)
        else:
            # Only discovery
            if discovery.has_any_server(timeout=check_timeout):
                print("Server available")
                sys.exit(0)
            else:
                print("No Server available")
                sys.exit(1)
    
    # MODE 2: Find server (get IP)
    elif args.find:
        # Determine timeout
        find_timeout = args.timeout if args.timeout != 2 else 5
        
        if args.no_discovery:
            # Only check specific IP
            if not args.target_ip:
                print("Error: --no-discovery requires --ip parameter", file=sys.stderr)
                sys.exit(1)
            
            if discovery.check_server_connection(args.target_ip, args.port):
                print(args.target_ip)
                sys.exit(0)
            else:
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
                print(found_ip)
                sys.exit(0)
            else:
                print("Warning: No server found", file=sys.stderr)
                sys.exit(1)

if __name__ == "__main__":
    main()
