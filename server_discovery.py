import socket
import sys
import argparse
import json
import time

class APServerDiscovery:
    """
    APServer Discovery and Connection Check Tool.
    
    This class provides methods to discover APServers in the network and check connections.
    Can be used programmatically or via command line.
    """
    
    def __init__(self, default_port=65432, discovery_port=65433):
        """
        Initialize the APServerDiscovery.
        
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

    def discover_servers(self, timeout=5):
        """
        Discover available APServers in the network using UDP broadcasts.
        
        Args:
            timeout (int): How long to listen for broadcasts in seconds
            
        Returns:
            list: List of discovered server information dictionaries
        """
        servers = []
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('', self.discovery_port))
                sock.settimeout(0.5)  # Kurzes Socket-Timeout für responsiveness
                
                start_time = time.time()
                seen_servers = set()
                last_server_time = start_time
                
                while time.time() - start_time < timeout:
                    try:
                        data, addr = sock.recvfrom(1024)
                        server_info = json.loads(data.decode('utf-8'))
                        
                        if server_info.get("service") == "APServer":
                            server_key = (server_info.get("ip"), server_info.get("port"))
                            if server_key not in seen_servers:
                                servers.append(server_info)
                                seen_servers.add(server_key)
                                last_server_time = time.time()
                                
                                # Früh beenden wenn Server gefunden und kurz gewartet
                                if len(servers) >= 1 and time.time() - last_server_time > 1:
                                    break
                        
                    except socket.timeout:
                        # Früh beenden wenn Server gefunden und lange nichts mehr kam
                        if servers and time.time() - last_server_time > 2:
                            break
                        continue
                    except (json.JSONDecodeError, Exception):
                        continue
                        
        except Exception:
            pass
        
        return servers

    def get_primary_server(self, timeout=5):
        """
        Get the first/primary server found via discovery.
        
        Args:
            timeout (int): Discovery timeout in seconds
            
        Returns:
            tuple: (ip, port) or (None, None) if not found
        """
        servers = self.discover_servers(timeout)
        if servers:
            server = servers[0]
            return (server['ip'], server['port'])
        return (None, None)

    def find_server(self, target_ip=None, target_port=None, discovery_timeout=5):
        """
        Find an APServer either by specific IP or via discovery.
        
        Args:
            target_ip (str): Specific IP to check first (optional)
            target_port (int): Server port to use (uses default_port if None)
            discovery_timeout (int): How long to search via discovery
            
        Returns:
            tuple: (ip, port) of found server or (None, None) if not found
        """
        if target_port is None:
            target_port = self.default_port
            
        # 1. Wenn spezifische IP angegeben, diese zuerst prüfen
        if target_ip:
            if self.check_server_connection(target_ip, target_port):
                return (target_ip, target_port)
        
        # 2. Falls spezifische IP nicht erreichbar oder nicht angegeben: Discovery verwenden
        discovered_ip, discovered_port = self.get_primary_server(discovery_timeout)
        
        if discovered_ip:
            # Discovered server nochmal testen (Discovery garantiert keine Erreichbarkeit)
            if self.check_server_connection(discovered_ip, discovered_port):
                return (discovered_ip, discovered_port)
        
        # 3. Nichts gefunden
        return (None, None)

    def get_server_ip(self, target_ip=None, target_port=None, discovery_timeout=5):
        """
        Get server IP address (convenience method for scripts).
        
        Args:
            target_ip (str): Specific IP to check first (optional)
            target_port (int): Server port to use (uses default_port if None)
            discovery_timeout (int): How long to search via discovery
            
        Returns:
            str or None: Server IP address or None if not found
        """
        found_ip, found_port = self.find_server(target_ip, target_port, discovery_timeout)
        return found_ip

# Backward compatibility - Module-level functions
def check_server_connection(host, port, timeout=2):
    """Backward compatibility function."""
    discovery = APServerDiscovery()
    return discovery.check_server_connection(host, port, timeout)

def discover_servers(timeout=5):
    """Backward compatibility function."""
    discovery = APServerDiscovery()
    return discovery.discover_servers(timeout)

def get_primary_server(timeout=5):
    """Backward compatibility function."""
    discovery = APServerDiscovery()
    return discovery.get_primary_server(timeout)

def find_server(target_ip=None, target_port=65432, discovery_timeout=5):
    """Backward compatibility function."""
    discovery = APServerDiscovery()
    return discovery.find_server(target_ip, target_port, discovery_timeout)

def main():
    parser = argparse.ArgumentParser(description="APServer Discovery and Connection Check Tool")
    
    parser.add_argument("--ip", "--host", dest="target_ip", 
                       help="Specific server IP address to check first")
    parser.add_argument("--port", type=int, default=65432,
                       help="Server port (default: 65432)")
    parser.add_argument("--no-discovery", action="store_true",
                       help="Disable discovery fallback")
    parser.add_argument("--timeout", type=int, default=5,
                       help="Discovery timeout in seconds (default: 5)")
    
    args = parser.parse_args()
    
    # Create discovery instance
    discovery = APServerDiscovery(default_port=args.port)
    
    # Server-Suche-Modus
    if args.no_discovery:
        # Nur spezifische IP prüfen
        if not args.target_ip:
            print("Warning: No server found - --no-discovery requires --ip parameter", file=sys.stderr)
            sys.exit(1)
        
        if discovery.check_server_connection(args.target_ip, args.port):
            print(args.target_ip)
            sys.exit(0)
        else:
            print("Warning: No server found", file=sys.stderr)
            sys.exit(1)
    else:
        # Normale Server-Suche (IP + Discovery fallback)
        found_ip, found_port = discovery.find_server(
            target_ip=args.target_ip,
            target_port=args.port,
            discovery_timeout=args.timeout
        )
        
        if found_ip:
            print(found_ip)  # Nur IP-Adresse
            sys.exit(0)
        else:
            print("Warning: No server found", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
