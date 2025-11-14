# Kasa Smart Plug Monitor for Washer & Dryer

**Real-time energy monitoring and notifications when your laundry cycles complete.**

This Python script monitors two Kasa smart plugs connected to your washer and dryer, tracks their power consumption, detects when cycles complete, and sends notifications to your iPhone.

---

## ⚠️ CRITICAL REQUIREMENTS

### **THESE MUST BE TRUE OR IT WON'T WORK:**

1. **Your Kasa smart plugs MUST support energy monitoring (EMeter)**
   - Models that work: HS110, KP115, EP10, EP25
   - Models that DON'T work: HS100, HS103, KP105 (no energy monitoring)
   - The script will check this and error out if not supported

2. **Your smart plugs MUST be on the same local network as the computer running this script**
   - No cloud/remote access support
   - Must have direct network access via WiFi/Ethernet

3. **This script must run continuously to monitor** (see Deployment Options below)
   - It's not a cloud service - you run it on your own hardware
   - If the script stops, monitoring stops

4. **Python 3.7+ required**

---

## 📱 iPhone Notifications via Pushover

**This guide uses Pushover** - the most reliable push notification service ($5 one-time purchase).

### Setup Pushover (5 minutes)

**Step 1: Purchase & Install Pushover App**
- App Store: https://apps.apple.com/us/app/pushover-notifications/id506088175
- Cost: $5 one-time (no subscription)

**Step 2: Create Account & Get Your User Key**
1. Go to https://pushover.net and create an account
2. After logging in, you'll see your dashboard
3. **YOUR USER KEY** is displayed at the top right - it looks like: `uQiRzpo4DXghDmr9QzzfQu27cmVRsG`
4. Copy this and save it - you'll need it for `PUSHOVER_USER_KEY`

**Step 3: Create an Application & Get API Token**
1. On your Pushover dashboard, scroll down and click **"Create an Application/API Token"**
2. Fill in:
   - Name: `Laundry Monitor` (or whatever you want)
   - Description: `Washer and dryer notifications`
   - URL: Leave blank
   - Icon: Optional
3. Click **"Create Application"**
4. **YOUR API TOKEN** will be displayed - it looks like: `azGDORePK8gMaC0QOYAMyEEuzJnyUi`
5. Copy this and save it - you'll need it for `PUSHOVER_APP_TOKEN`

**Step 4: Set Environment Variables**

```bash
export PUSHOVER_APP_TOKEN=azGDORePK8gMaC0QOYAMyEEuzJnyUi  # From Step 3
export PUSHOVER_USER_KEY=uQiRzpo4DXghDmr9QzzfQu27cmVRsG   # From Step 2
```

**That's it!** Notifications will now arrive on your iPhone.

---

### Alternative: Other Notification Services

<details>
<summary>Click to see ntfy.sh (free, no signup) or Telegram options</summary>

#### ntfy.sh (FREE - NO SIGNUP)

1. Install ntfy app from App Store: https://apps.apple.com/us/app/ntfy/id1625396347
2. Open app and subscribe to a topic (e.g., "mylaundry-12345")
3. Set environment variable: `export NTFY_TOPIC=mylaundry-12345`

#### Telegram (FREE - REQUIRES BOT SETUP)

1. Install Telegram from App Store
2. Create a bot via @BotFather on Telegram
3. Get your chat ID by messaging @userinfobot
4. Set environment variables:
   ```bash
   export TELEGRAM_BOT_TOKEN=your_bot_token
   export TELEGRAM_CHAT_ID=your_chat_id
   ```

</details>

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
cd /home/user/experiments/kasa-smart-plug

# Install required Python packages
pip install python-kasa requests
```

### Step 2: Discover Your Devices

```bash
python monitor.py discover
```

This will scan your network and show all Kasa devices with their IP addresses:

```
Found 2 device(s):
  • Washer Plug - 192.168.1.100 - Energy monitoring: ✓
  • Dryer Plug - 192.168.1.101 - Energy monitoring: ✓
```

**⚠️ If energy monitoring shows ✗, that plug will NOT work!**

### Step 3: Configure Environment Variables

Create a file to store your configuration (or add to `.bashrc` / `.zshrc`):

```bash
# Required: IP addresses of your smart plugs (from Step 2)
export WASHER_IP=192.168.1.100
export DRYER_IP=192.168.1.101

# Required: Pushover credentials (from Pushover setup above)
export PUSHOVER_APP_TOKEN=azGDORePK8gMaC0QOYAMyEEuzJnyUi  # Your API token
export PUSHOVER_USER_KEY=uQiRzpo4DXghDmr9QzzfQu27cmVRsG   # Your user key

# Optional: Fine-tune detection thresholds
export WASHER_POWER_START=5.0        # Watts to consider "started"
export WASHER_POWER_RUNNING=3.0      # Watts to consider still running
export WASHER_IDLE_TIME=120          # Seconds idle before "done"

export DRYER_POWER_START=100.0       # Dryers use much more power
export DRYER_POWER_RUNNING=50.0
export DRYER_IDLE_TIME=180           # Dryers often have cool-down periods

export CHECK_INTERVAL=10             # Seconds between power checks
```

Load your configuration:

```bash
source config.env  # or wherever you saved it
```

### Step 4: Run the Monitor

```bash
python monitor.py
```

You should see:

```
============================================================
🔌 Kasa Smart Plug Monitor Started
============================================================
Monitoring interval: 10 seconds
Washer idle threshold: 120 seconds
Dryer idle threshold: 180 seconds
Press Ctrl+C to stop

Washer: idle (0.2W) | Dryer: idle (0.1W)
```

### Step 5: Test It!

Start your washer or dryer. You should see:

```
🟢 Washer cycle STARTED (Power: 245.3W)
```

When it completes (after power drops below threshold for configured time):

```
✅ Washer cycle COMPLETE!
Duration: 45 minutes
Final power: 0.8W
```

And you'll get a notification on your iPhone! 📱

---

## ⚙️ How It Works

### Power Monitoring

The script checks power consumption every 10 seconds (configurable) and uses a state machine:

1. **IDLE** → Waiting for power usage to spike above start threshold
2. **RUNNING** → Cycle in progress, power above running threshold
3. **FINISHING** → Power dropped below threshold, counting idle time
4. **IDLE** → Idle time exceeded threshold, cycle complete! Send notification.

### Default Thresholds

**Washer:**
- Start: 5W (washers use power during fill, agitate, spin)
- Running: 3W
- Idle time: 2 minutes

**Dryer:**
- Start: 100W (dryers use much more power for heating)
- Running: 50W
- Idle time: 3 minutes (dryers often tumble after heat stops)

**You may need to adjust these based on your appliances!**

To find the right values:
1. Watch the log while running a cycle
2. Note the typical power draw
3. Adjust thresholds accordingly

---

## 🖥️ WHERE TO RUN THIS (CRITICAL!)

### ❌ CLOUD HOSTING WON'T WORK ❌

**You CANNOT run this on Railway, Heroku, AWS, Google Cloud, DigitalOcean, or ANY cloud service.**

**Why?**
- Kasa smart plugs have NO cloud API
- They ONLY work on your local home network
- Railway/cloud servers cannot reach devices on your home WiFi
- There's no way to "expose" your plugs to the internet safely

**Think of it like this:** Your smart plugs are like devices on your home WiFi that can only be talked to by other devices on the same WiFi. A server in a data center in Virginia can't talk to your washing machine in your house.

---

### ✅ WHAT WILL WORK

You need something running **24/7 on your home network**:

### Option 1: Raspberry Pi (STRONGLY RECOMMENDED)

**This is the best solution.**

- **Cost:** $35-50 for Raspberry Pi Zero 2 W or Pi 4
- **Power:** Uses ~$2-3/year in electricity
- **Setup:** 30 minutes
- **Maintenance:** Zero after setup

**Why it's perfect:**
- Tiny - size of a credit card
- Silent - no fans
- Runs 24/7 reliably
- On your home network with your plugs
- Can sit next to your router

**Setup:**
1. Buy Raspberry Pi with case and power supply
2. Install Raspberry Pi OS Lite (headless)
3. Connect to your WiFi
4. Install Python and this script
5. Set up as systemd service (see Advanced section)
6. Forget about it - runs forever

### Option 2: Always-On Computer / Home Server

- Desktop computer that runs 24/7
- Home server or NAS (Synology, QNAP, Unraid, etc.)
- Old laptop plugged in permanently

**Pros:** You might already have this
**Cons:** Uses more power than Raspberry Pi

### Option 3: Your Main Computer

**Only for testing!**
- Script only runs when computer is on
- Stops monitoring when computer sleeps
- Fine for testing, not for production use

---

### Can I Access This Remotely?

**Short answer:** The smart plugs can't be accessed remotely, but notifications work anywhere.

**What works:**
- ✅ Notifications to your iPhone work anywhere (via Pushover servers)
- ✅ You can SSH into your Raspberry Pi from anywhere to check status
- ✅ You can set up a VPN to your home network to access everything

**What doesn't work:**
- ❌ Moving the script to the cloud
- ❌ Accessing the plugs when not on your home WiFi (without VPN)
- ❌ Any solution that doesn't have the script running on your local network

---

### Bottom Line

**Buy a Raspberry Pi ($35) or use an old computer that runs 24/7 on your home network.**

That's the only way this can work. No cloud service will work because smart plugs don't have internet access - they only work locally.

---

## 🔧 Advanced: Running as a System Service (Linux)

Create `/etc/systemd/system/kasa-monitor.service`:

```ini
[Unit]
Description=Kasa Smart Plug Monitor
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/user/experiments/kasa-smart-plug
Environment="WASHER_IP=192.168.1.100"
Environment="DRYER_IP=192.168.1.101"
Environment="PUSHOVER_APP_TOKEN=your_api_token_here"
Environment="PUSHOVER_USER_KEY=your_user_key_here"
ExecStart=/usr/bin/python3 /home/user/experiments/kasa-smart-plug/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable kasa-monitor
sudo systemctl start kasa-monitor
sudo systemctl status kasa-monitor
```

View logs:

```bash
sudo journalctl -u kasa-monitor -f
```

---

## 📊 Logs

All activity is logged to:
- Console output (stdout)
- `kasa_monitor.log` in the script directory

Logs include:
- Connection status
- Cycle start/stop events
- Power readings every minute
- Notification delivery status
- Errors and warnings

---

## 🐛 Troubleshooting

### "ERROR: python-kasa library not installed!"

```bash
pip install python-kasa
```

### "No Kasa devices found on network"

- Make sure plugs are set up in Kasa app first
- Verify plugs are on same WiFi network as computer
- Check firewall isn't blocking local network discovery
- Try specifying IPs directly instead of discovery

### "ERROR: Device does not support energy monitoring!"

Your plug model doesn't have EMeter. You need:
- HS110, KP115, EP10, EP25 (have EMeter ✓)
- NOT HS100, HS103, KP105 (no EMeter ✗)

Check: https://www.kasasmart.com/us/products/smart-plugs

### "Failed to connect to device"

- Verify IP address is correct (may change if DHCP)
- Set static IPs in your router for the plugs
- Check network connectivity: `ping 192.168.1.100`

### Not detecting cycle completion

- Check power thresholds are appropriate for your appliance
- Watch the logs during a cycle to see power patterns
- Adjust `POWER_START`, `POWER_RUNNING`, and `IDLE_TIME` variables
- Some appliances have standby power - set running threshold above that

### No notifications received

- Check environment variables are set correctly
- Verify notification service (ntfy app, Pushover, etc.) is installed
- Check logs for "notification sent" confirmation
- Test notification service independently

---

## 💡 Tips & Tricks

### Static IP Addresses

Set static IPs for your smart plugs in your router's DHCP settings so they don't change!

### Power Threshold Calibration

Run the script and watch one complete cycle while noting power values:

```
Washer: running (234.5W)
Washer: running (187.3W)
Washer: running (456.2W)  # Spin cycle
Washer: running (12.4W)   # Drain pump
Washer: running (1.2W)    # Done!
```

Set `POWER_RUNNING` above the final values but below active operation.

### Multiple Notification Services

You can enable multiple services simultaneously! Set up both ntfy AND Pushover to ensure you never miss a notification.

### Testing Notifications

Manually send a test notification to verify setup:

```bash
# Test ntfy
curl -d "Test notification" https://ntfy.sh/mylaundry-12345

# Test Pushover
curl -s \
  --form-string "token=YOUR_APP_TOKEN" \
  --form-string "user=YOUR_USER_KEY" \
  --form-string "message=Test notification" \
  https://api.pushover.net/1/messages.json
```

---

## 📝 License

MIT License - Use freely!

---

## 🤝 Support

Issues? Questions?

1. Check the troubleshooting section above
2. Review logs in `kasa_monitor.log`
3. Verify your smart plug model supports energy monitoring
4. Test with `python monitor.py discover` first

---

**Made with ☕ for people tired of checking the laundry room**
