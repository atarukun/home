# Christmas App Debugging Guide

## Debug Log File

The Christmas app now logs detailed debug information to help diagnose WiFi connection and date fetching issues.

### Log Location

The debug log is written to: `/christmas_debug.log`

### Accessing the Log

To read the debug log:

1. Put your badge into USB Disk Mode:
   - Connect via USB-C cable
   - Press the RESET button twice
   - The "USB Disk Mode" screen will appear
   - Badge appears as "BADGER" disk on your computer

2. Navigate to the root of the BADGER disk

3. Open the file `christmas_debug.log` in a text editor

### What's Logged

The log contains timestamped entries (seconds since boot) including:

**WiFi Connection:**
- WiFi scan attempts and results
- Number of networks found
- Whether the target SSID was found
- Connection attempts and status
- Timeout information
- Any connection errors

**Date Fetching:**
- API call attempts to multiple time services (WorldTimeAPI, TimeAPI.io, AISENSE, OpenTimezone)
- Which API is being tried (e.g., "Trying API 1/4")
- Response data received (size in bytes)
- Datetime strings from API
- Parsing success/failure
- Error messages with exception types
- Automatic fallback to next API when one fails
- Retry timing information
- Round-robin API rotation to distribute load

### On-Screen Status

While debugging, the screen shows:

**When connecting:**
- "connecting Xs" - Shows elapsed connection time in seconds
- "log: /christmas_debug.log" - Shows where debug info is saved

**When connected but no date:**
- "fetching date..." - Currently attempting to fetch from API
- "{error_type} (Xs)" - Shows error type with retry countdown (e.g., "timeout (3s)", "dns_fail (2s)")
- "log: /christmas_debug.log" - Shows where debug info is saved

**When working:**
- Countdown to Christmas
- Current date at bottom

### Common Issues to Look For

1. **WiFi SSID not found**
   - Check if the SSID in `/badge/secrets.py` is correct
   - Verify the network is 2.4GHz (not 5GHz)
   - Check if network is in range

2. **Connection timeout**
   - Check WiFi password in `/badge/secrets.py`
   - Verify network allows new device connections

3. **API call failures**
   - The app tries multiple time APIs automatically (4 different services)
   - If all APIs fail, will show "all_failed" error
   - Check for network connectivity issues
   - Look for timeout errors (3 second timeout per API)
   - Check for DNS resolution problems
   - Verify internet access from WiFi network
   - Check debug log to see which APIs were tried and why they failed

4. **Parse errors**
   - May indicate API format changed or returned unexpected data
   - The app supports multiple API response formats
   - Check the datetime string in the log
   - If one API fails, the app automatically tries others

### API Rotation and Load Distribution

The app uses a round-robin approach to distribute load across multiple time APIs:

1. **4 Time APIs Available:**
   - WorldTimeAPI (worldtimeapi.org)
   - TimeAPI.io (timeapi.io)
   - AISENSE (aisense.no)
   - OpenTimezone (opentimezone.com)

2. **Automatic Fallback:**
   - If one API fails, automatically tries the next one
   - Tries all 4 APIs before giving up
   - Each API has a 3-second timeout

3. **Load Distribution:**
   - Rotates through APIs in round-robin fashion
   - Helps avoid hitting rate limits on any single service
   - Ensures better reliability if one service goes down
