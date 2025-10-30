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
- API call attempts to worldtimeapi.org
- Response data received (size in bytes)
- Datetime strings from API
- Parsing success/failure
- Error messages with exception types
- Retry timing information

### On-Screen Status

While debugging, the screen shows:

**When connecting:**
- "connecting Xs" - Shows elapsed connection time in seconds
- "log: /christmas_debug.log" - Shows where debug info is saved

**When connected but no date:**
- "fetching date..." - Currently attempting to fetch from API
- "retry in Xs" - Waiting to retry after failure (countdown)
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
   - Check for network connectivity issues
   - Look for timeout errors (3 second timeout)
   - Check for DNS resolution problems
   - Verify internet access from WiFi network

4. **Parse errors**
   - May indicate API format changed
   - Check the datetime string in the log
