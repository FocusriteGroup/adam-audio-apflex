"""
Base Serial Device Manager

Common retry logic and service integration for all serial device managers.
Provides consistent error handling and communication patterns for serial devices.
"""

import time
import logging
from datetime import datetime

class BaseSerialManager:
    """Base class for all serial device managers with retry logic."""
    
    def __init__(self, workstation_id, device_name):
        """
        Initialize base serial device manager.
        
        Args:
            workstation_id (str): Workstation identifier
            device_name (str): Device name for logging
        """
        self.workstation_id = workstation_id
        self.device_name = device_name
        self.logger = logging.getLogger(f"AdamSerial{device_name}")
        
    def execute_with_retry(self, operation_func, operation_name, 
                          max_retries=2, retry_delay=0.5, *args, **kwargs):
        """
        Execute serial device operation with retry logic.
        
        Args:
            operation_func: Function to execute (must accept 'attempt' as first arg)
            operation_name: Name for logging
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries
            *args, **kwargs: Arguments for operation_func
            
        Returns:
            Result from operation_func
            
        Raises:
            Exception: Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    self.logger.info("%s retry attempt %d/%d after %.1f second delay", 
                                   operation_name, attempt, max_retries, retry_delay)
                    time.sleep(retry_delay)
                
                return operation_func(attempt, *args, **kwargs)
                
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    self.logger.warning("%s attempt %d/%d failed: %s", 
                                      operation_name, attempt + 1, max_retries + 1, e)
                    self._reset_serial_connection()
                else:
                    self.logger.error("All %s attempts failed. Last error: %s", operation_name, e)
        
        # Alle Versuche fehlgeschlagen
        raise last_exception
    
    def _reset_serial_connection(self):
        """Override in subclass for device-specific serial reset logic."""
        self.logger.debug("Base serial reset - override in subclass for device-specific reset")
        
    def _wait_for_serial_device_ready(self, device, device_type, timeout=5.0, retry_interval=0.1):
        """
        Wait for serial device to be ready with timeout.
        
        Args:
            device: Serial hardware device object
            device_type: Device type for logging
            timeout: Maximum time to wait in seconds
            retry_interval: Time between connection checks
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if device.connected:
                    self.logger.info("%s serial connection confirmed after %.1f seconds", 
                                   device_type, time.time() - start_time)
                    return
                time.sleep(retry_interval)
            except Exception as e:
                self.logger.debug("%s serial connection check failed: %s", device_type, e)
                time.sleep(retry_interval)
        
        self.logger.warning("%s serial device not ready after %.1f seconds - proceeding anyway", device_type, timeout)

    def _ensure_serial_device_connected(self, device, device_type, max_checks=3, check_delay=0.1):
        """
        Ensure serial device is connected with multiple checks.
        
        Args:
            device: Serial hardware device object
            device_type: Device type for logging
            max_checks: Maximum number of connection checks
            check_delay: Delay between checks in seconds
            
        Returns:
            bool: True if device is connected, False otherwise
        """
        for check in range(max_checks):
            try:
                if device.connected:
                    self.logger.debug("%s serial connection confirmed on check %d/%d", 
                                    device_type, check + 1, max_checks)
                    return True
                
                if check < max_checks - 1:
                    self.logger.debug("%s serial connection check %d/%d failed, retrying...", 
                                    device_type, check + 1, max_checks)
                    time.sleep(check_delay)
                    
            except Exception as e:
                self.logger.debug("Serial connection check %d/%d failed with exception: %s", 
                                check + 1, max_checks, e)
                if check < max_checks - 1:
                    time.sleep(check_delay)
        
        self.logger.warning("%s serial connection could not be confirmed after %d checks", 
                          device_type, max_checks)
        return False

    def _log_to_service(self, log_data, service_host, service_port):
        """Log serial device operation to service."""
        from services import WorkstationLogger
        WorkstationLogger.send_log_to_service(
            self.workstation_id, log_data, service_host, service_port
        )