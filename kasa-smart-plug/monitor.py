#!/usr/bin/env python3
"""
Kasa Smart Plug Monitor for Washer and Dryer
Monitors energy usage and sends notifications when appliance cycles complete
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, Optional
import logging
from dataclasses import dataclass
from enum import Enum

try:
    from kasa import Discover, SmartPlug
except ImportError:
    print("ERROR: python-kasa library not installed!")
    print("Install with: pip install python-kasa")
    sys.exit(1)

# Optional notification libraries
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("WARNING: requests library not installed. Install with: pip install requests")


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kasa_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ApplianceState(Enum):
    """States for appliance operation"""
    IDLE = "idle"
    RUNNING = "running"
    FINISHING = "finishing"


@dataclass
class ApplianceConfig:
    """Configuration for an appliance"""
    name: str
    device_ip: str
    power_threshold_start: float = 5.0  # Watts to consider "started"
    power_threshold_running: float = 3.0  # Watts to consider still "running"
    idle_time_threshold: int = 120  # Seconds below threshold to consider "done"
    check_interval: int = 10  # Seconds between checks


class ApplianceMonitor:
    """Monitor for a single appliance"""

    def __init__(self, config: ApplianceConfig):
        self.config = config
        self.state = ApplianceState.IDLE
        self.device: Optional[SmartPlug] = None
        self.idle_start_time: Optional[datetime] = None
        self.cycle_start_time: Optional[datetime] = None
        self.last_power: float = 0.0

    async def connect(self) -> bool:
        """Connect to the smart plug"""
        try:
            logger.info(f"Connecting to {self.config.name} at {self.config.device_ip}...")
            self.device = SmartPlug(self.config.device_ip)
            await self.device.update()
            logger.info(f"Connected to {self.config.name}: {self.device.alias}")

            # Check if device supports energy monitoring
            if not self.device.has_emeter:
                logger.error(f"ERROR: {self.config.name} does not support energy monitoring!")
                return False

            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.config.name}: {e}")
            return False

    async def get_current_power(self) -> Optional[float]:
        """Get current power consumption in watts"""
        try:
            await self.device.update()
            emeter = await self.device.get_emeter_realtime()
            power = emeter.get('power_mw', 0) / 1000.0  # Convert mW to W
            return power
        except Exception as e:
            logger.error(f"Error reading power from {self.config.name}: {e}")
            return None

    async def check_state(self) -> Optional[str]:
        """Check appliance state and return notification message if cycle complete"""
        power = await self.get_current_power()
        if power is None:
            return None

        self.last_power = power
        current_time = datetime.now()

        # State machine logic
        if self.state == ApplianceState.IDLE:
            if power >= self.config.power_threshold_start:
                self.state = ApplianceState.RUNNING
                self.cycle_start_time = current_time
                self.idle_start_time = None
                logger.info(f"🟢 {self.config.name} cycle STARTED (Power: {power:.1f}W)")

        elif self.state == ApplianceState.RUNNING:
            if power < self.config.power_threshold_running:
                # Power dropped, might be finishing
                if self.idle_start_time is None:
                    self.idle_start_time = current_time
                    self.state = ApplianceState.FINISHING
                    logger.info(f"🟡 {self.config.name} power dropped, monitoring for completion...")
            else:
                # Still running strong
                self.idle_start_time = None

        elif self.state == ApplianceState.FINISHING:
            if power >= self.config.power_threshold_running:
                # Power came back up, still running
                self.state = ApplianceState.RUNNING
                self.idle_start_time = None
                logger.info(f"🟢 {self.config.name} resumed running (Power: {power:.1f}W)")
            else:
                # Check if idle long enough
                idle_duration = (current_time - self.idle_start_time).total_seconds()
                if idle_duration >= self.config.idle_time_threshold:
                    # Cycle complete!
                    cycle_duration = (current_time - self.cycle_start_time).total_seconds()
                    message = (
                        f"✅ {self.config.name} cycle COMPLETE!\n"
                        f"Duration: {cycle_duration/60:.0f} minutes\n"
                        f"Final power: {power:.1f}W"
                    )
                    logger.info(f"🔵 {message}")
                    self.state = ApplianceState.IDLE
                    self.idle_start_time = None
                    self.cycle_start_time = None
                    return message

        return None


class NotificationService:
    """Handle notifications via multiple services"""

    def __init__(self):
        # Pushover configuration
        self.pushover_token = os.getenv('PUSHOVER_APP_TOKEN')
        self.pushover_user = os.getenv('PUSHOVER_USER_KEY')

        # ntfy.sh configuration
        self.ntfy_topic = os.getenv('NTFY_TOPIC')

        # Telegram configuration
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

    async def send(self, message: str):
        """Send notification via all configured services"""
        if not REQUESTS_AVAILABLE:
            logger.warning("Requests library not available, cannot send notifications")
            return

        # Try Pushover
        if self.pushover_token and self.pushover_user:
            await self._send_pushover(message)

        # Try ntfy.sh
        if self.ntfy_topic:
            await self._send_ntfy(message)

        # Try Telegram
        if self.telegram_bot_token and self.telegram_chat_id:
            await self._send_telegram(message)

        # If nothing configured, log warning
        if not any([self.pushover_token, self.ntfy_topic, self.telegram_bot_token]):
            logger.warning("No notification service configured!")
            logger.info(f"Message would have been: {message}")

    async def _send_pushover(self, message: str):
        """Send via Pushover"""
        try:
            response = requests.post(
                'https://api.pushover.net/1/messages.json',
                data={
                    'token': self.pushover_token,
                    'user': self.pushover_user,
                    'message': message,
                    'title': 'Laundry Alert',
                    'priority': 1,
                    'sound': 'pushover'
                },
                timeout=10
            )
            if response.status_code == 200:
                logger.info("✓ Pushover notification sent")
            else:
                logger.error(f"Pushover error: {response.text}")
        except Exception as e:
            logger.error(f"Failed to send Pushover notification: {e}")

    async def _send_ntfy(self, message: str):
        """Send via ntfy.sh"""
        try:
            response = requests.post(
                f'https://ntfy.sh/{self.ntfy_topic}',
                data=message.encode('utf-8'),
                headers={
                    'Title': 'Laundry Alert',
                    'Priority': 'high',
                    'Tags': 'white_check_mark'
                },
                timeout=10
            )
            if response.status_code == 200:
                logger.info("✓ ntfy notification sent")
            else:
                logger.error(f"ntfy error: {response.text}")
        except Exception as e:
            logger.error(f"Failed to send ntfy notification: {e}")

    async def _send_telegram(self, message: str):
        """Send via Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            response = requests.post(
                url,
                json={
                    'chat_id': self.telegram_chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                },
                timeout=10
            )
            if response.status_code == 200:
                logger.info("✓ Telegram notification sent")
            else:
                logger.error(f"Telegram error: {response.text}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")


async def discover_devices():
    """Discover Kasa devices on network"""
    logger.info("Discovering Kasa devices on network...")
    try:
        devices = await Discover.discover()
        if not devices:
            logger.warning("No Kasa devices found on network")
            return

        logger.info(f"\nFound {len(devices)} device(s):")
        for ip, device in devices.items():
            await device.update()
            emeter_support = "✓" if device.has_emeter else "✗"
            logger.info(f"  • {device.alias} - {ip} - Energy monitoring: {emeter_support}")
        logger.info("")
    except Exception as e:
        logger.error(f"Error discovering devices: {e}")


async def main():
    """Main monitoring loop"""

    # Check if discovery mode
    if len(sys.argv) > 1 and sys.argv[1] == 'discover':
        await discover_devices()
        return

    # Load configuration from environment
    washer_ip = os.getenv('WASHER_IP')
    dryer_ip = os.getenv('DRYER_IP')

    if not washer_ip or not dryer_ip:
        logger.error("ERROR: WASHER_IP and DRYER_IP environment variables must be set!")
        logger.info("\nRun with 'python monitor.py discover' to find your devices")
        logger.info("Then set environment variables:")
        logger.info("  export WASHER_IP=192.168.1.xxx")
        logger.info("  export DRYER_IP=192.168.1.xxx")
        sys.exit(1)

    # Create appliance monitors
    washer_config = ApplianceConfig(
        name="Washer",
        device_ip=washer_ip,
        power_threshold_start=float(os.getenv('WASHER_POWER_START', '5.0')),
        power_threshold_running=float(os.getenv('WASHER_POWER_RUNNING', '3.0')),
        idle_time_threshold=int(os.getenv('WASHER_IDLE_TIME', '120')),
        check_interval=int(os.getenv('CHECK_INTERVAL', '10'))
    )

    dryer_config = ApplianceConfig(
        name="Dryer",
        device_ip=dryer_ip,
        power_threshold_start=float(os.getenv('DRYER_POWER_START', '100.0')),
        power_threshold_running=float(os.getenv('DRYER_POWER_RUNNING', '50.0')),
        idle_time_threshold=int(os.getenv('DRYER_IDLE_TIME', '180')),
        check_interval=int(os.getenv('CHECK_INTERVAL', '10'))
    )

    washer = ApplianceMonitor(washer_config)
    dryer = ApplianceMonitor(dryer_config)
    notifier = NotificationService()

    # Connect to devices
    washer_connected = await washer.connect()
    dryer_connected = await dryer.connect()

    if not washer_connected and not dryer_connected:
        logger.error("Failed to connect to any devices. Exiting.")
        sys.exit(1)

    logger.info("\n" + "="*60)
    logger.info("🔌 Kasa Smart Plug Monitor Started")
    logger.info("="*60)
    logger.info(f"Monitoring interval: {washer_config.check_interval} seconds")
    logger.info(f"Washer idle threshold: {washer_config.idle_time_threshold} seconds")
    logger.info(f"Dryer idle threshold: {dryer_config.idle_time_threshold} seconds")
    logger.info("Press Ctrl+C to stop\n")

    # Main monitoring loop
    try:
        while True:
            tasks = []

            if washer_connected:
                tasks.append(washer.check_state())
            if dryer_connected:
                tasks.append(dryer.check_state())

            results = await asyncio.gather(*tasks)

            # Send notifications for completed cycles
            for message in results:
                if message:
                    await notifier.send(message)

            # Status update every minute
            if datetime.now().second < washer_config.check_interval:
                status_lines = []
                if washer_connected:
                    status_lines.append(
                        f"Washer: {washer.state.value} ({washer.last_power:.1f}W)"
                    )
                if dryer_connected:
                    status_lines.append(
                        f"Dryer: {dryer.state.value} ({dryer.last_power:.1f}W)"
                    )
                logger.info(" | ".join(status_lines))

            await asyncio.sleep(washer_config.check_interval)

    except KeyboardInterrupt:
        logger.info("\n\nMonitoring stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
