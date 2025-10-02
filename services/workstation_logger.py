"""
Workstation Service Communication

Centralized logging service for workstation operations.
Handles communication with ADAM service for central logging.
"""

import socket
import json
import logging

WORKSTATION_LOGGER = logging.getLogger("AdamWorkstation")

class WorkstationLogger:
    """Centralized logging utilities for workstation features."""
    
    @staticmethod
    def send_log_to_service(workstation_id, log_data, service_host, service_port=65432):
        """
        Send log data to ADAM service for central logging.
        
        Args:
            workstation_id (str): Workstation identifier
            log_data (dict): Log data to send to service
            service_host (str): Service host
            service_port (int): Service port
            
        Returns:
            bool: True if logging successful, False otherwise
        """
        if not service_host:
            WORKSTATION_LOGGER.warning("No service host available for logging")
            return False
            
        try:
            log_command = {
                "action": "log_workstation_task",
                "workstation_id": workstation_id,
                **log_data
            }
            
            WORKSTATION_LOGGER.info("Sending log to service: %s", log_command)
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.settimeout(5.0)
                client_socket.connect((service_host, service_port))
                client_socket.send(json.dumps(log_command).encode("utf-8"))
                response = client_socket.recv(1024).decode("utf-8")
                
                if response and "logged" in response:
                    WORKSTATION_LOGGER.info("Log successfully sent to service")
                    return True
                else:
                    WORKSTATION_LOGGER.warning("Service logging failed: %s", response)
                    return False
                    
        except Exception as e:
            WORKSTATION_LOGGER.error("Error sending log to service: %s", e)
            return False