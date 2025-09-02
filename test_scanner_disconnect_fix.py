#!/usr/bin/env python3
"""
Simple test to verify Honeywell Scanner disconnection detection fix
"""

import time
import logging
from datetime import datetime
from ap_utils import HoneywellScanner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] %(message)s"
)

logger = logging.getLogger("ScannerDisconnectTest")

class SimpleDisconnectTest:
    """Simple test for scanner disconnection detection."""
    
    def __init__(self):
        """Initialize the test."""
        self.scanner = None
        self.events = []
        
    def on_connect(self):
        """Connection callback."""
        event = f"CONNECTED at {datetime.now().strftime('%H:%M:%S')}"
        self.events.append(event)
        logger.info(event)
        print(f"✅ {event}")
        
    def on_disconnect(self):
        """Disconnection callback."""
        event = f"DISCONNECTED at {datetime.now().strftime('%H:%M:%S')}"
        self.events.append(event)
        logger.warning(event)
        print(f"❌ {event}")
        
    def run_test(self):
        """Run the disconnect test."""
        print("🔍 Testing Honeywell Scanner Disconnection Detection")
        print("="*55)
        
        # Initialize scanner
        print("🚀 Initializing scanner...")
        self.scanner = HoneywellScanner(
            baudrate=9600,
            product_id=0x0B6A,
            vendor_id=0x0C2E,
            timeout=10,
            retry_interval=2,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect
        )
        
        # Wait for connection
        print("⏳ Waiting for scanner to connect...")
        start_time = time.time()
        while time.time() - start_time < 30:
            if self.scanner.connected:
                break
            time.sleep(1)
            print(".", end="", flush=True)
            
        if not self.scanner.connected:
            print("\n❌ Scanner did not connect within 30 seconds")
            return False
            
        print(f"\n✅ Scanner connected on {self.scanner._current_port}")
        
        # Monitor for disconnection/reconnection
        print("\n👀 Monitoring for 60 seconds...")
        print("   Please disconnect and reconnect the scanner during this time")
        
        for i in range(60):
            status = "✅" if self.scanner.connected else "❌"
            port = getattr(self.scanner, '_current_port', 'None')
            
            if i % 10 == 0:  # Status every 10 seconds
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"🕐 {timestamp} - Status: {status} Port: {port}")
                
            time.sleep(1)
            
        # Cleanup
        print("\n🧹 Cleaning up...")
        self.scanner.disconnect()
        
        # Summary
        print("\n📋 TEST SUMMARY")
        print("="*30)
        print(f"Total events: {len(self.events)}")
        for event in self.events:
            print(f"  • {event}")
            
        return len(self.events) > 1  # Success if we got more than just initial connection


def main():
    """Main function."""
    test = SimpleDisconnectTest()
    
    try:
        success = test.run_test()
        if success:
            print("\n🎉 Test PASSED - Disconnection detection is working!")
        else:
            print("\n⚠️  Test FAILED - Only initial connection detected")
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return 1
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
