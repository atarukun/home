import time
import random
import sys
from badgeware import screen, PixelFont, shapes, brushes, io, run, Matrix

try:
    from urllib.urequest import urlopen
    import json
    import network
    NETWORK_AVAILABLE = True
except ImportError:
    NETWORK_AVAILABLE = False

# Christmas colors
BG_COLOR = (10, 20, 40)  # Dark blue night sky
TEXT_COLOR = (255, 255, 255)  # White text
SNOWFLAKE_COLOR = (240, 248, 255)  # Light snow color

# Pre-create brushes for performance
BG_BRUSH = brushes.color(*BG_COLOR)
TEXT_BRUSH = brushes.color(*TEXT_COLOR)
SNOWFLAKE_BRUSH = brushes.color(*SNOWFLAKE_COLOR)

# Load font
large_font = PixelFont.load("/system/assets/fonts/ziplock.ppf")
small_font = PixelFont.load("/system/assets/fonts/nope.ppf")

class Snowflake:
    """A single falling snowflake"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset snowflake to top of screen with random properties"""
        self.x = random.randint(0, 160)
        self.y = random.randint(-20, 0)  # Start slightly above screen
        self.size = random.randint(1, 2)  # Small snowflakes
        self.speed = random.uniform(0.3, 0.8)  # Gentle fall speed
        self.drift = random.uniform(-0.2, 0.2)  # Slight horizontal drift
    
    def update(self):
        """Update snowflake position"""
        self.y += self.speed
        self.x += self.drift
        
        # Reset if fallen off screen
        if self.y > 120:
            self.reset()
        
        # Wrap horizontally
        if self.x < 0:
            self.x = 160
        elif self.x > 160:
            self.x = 0
    
    def draw(self):
        """Draw the snowflake"""
        screen.brush = SNOWFLAKE_BRUSH
        screen.draw(shapes.circle(int(self.x), int(self.y), self.size))

# Create snowflakes
snowflakes = [Snowflake() for _ in range(15)]

# Base days in each month (non-leap year)
BASE_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# Month names (short format)
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Cache for fetched time data
_cached_time = None
_last_fetch_attempt = 0
_fetch_success = False
_last_error_type = None  # Track last error for on-screen display
_current_api_index = 0  # Track which API to try next
FETCH_INTERVAL = 60 * 60 * 1000  # Try to fetch once per hour (in milliseconds) when successful
RETRY_INTERVAL = 5 * 1000  # Retry every 5 seconds (in milliseconds) when failed
MAX_ERROR_TYPE_LENGTH = 10  # Maximum characters to display for error type

# Multiple time API endpoints for fallback support
# Each entry is (url, parse_function_name)
TIME_APIS = [
    # WorldTimeAPI - returns {"datetime": "2025-10-30T01:23:45.123456+00:00", ...}
    ("https://worldtimeapi.org/api/timezone/Etc/UTC", "parse_worldtime"),
    # TimeAPI.io - returns {"year": 2025, "month": 10, "day": 30, ...}
    ("https://www.timeapi.io/api/Time/current/zone?timeZone=UTC", "parse_timeapi"),
    # AISENSE API - returns {"datetime": "2025-10-30T01:23:45Z", ...}
    ("https://aisense.no/api/v1/datetime", "parse_aisense"),
    # OpenTimezone API - returns {"datetime": "2025-10-30T01:23:45Z", ...}
    ("https://api.opentimezone.com/current?timezone=UTC", "parse_opentimezone"),
]

# Network connection state
WIFI_TIMEOUT = 60
WIFI_PASSWORD = None
WIFI_SSID = None
wlan = None
connected = False
ticks_start = None

# Debug logging
DEBUG_LOG_FILE = "/christmas_debug.log"
def debug_log(message):
    """Log debug messages to a file for later inspection"""
    try:
        import time
        timestamp = io.ticks / 1000.0  # seconds since boot
        with open(DEBUG_LOG_FILE, "a") as f:
            f.write(f"[{timestamp:8.1f}s] {message}\n")
    except Exception:
        # Silently fail if logging doesn't work
        pass

def get_connection_details():
    """Get WiFi credentials from secrets.py"""
    global WIFI_PASSWORD, WIFI_SSID

    if WIFI_SSID is not None:
        return True

    try:
        sys.path.insert(0, "/")
        from secrets import WIFI_PASSWORD, WIFI_SSID
        sys.path.pop(0)
    except ImportError:
        WIFI_PASSWORD = None
        WIFI_SSID = None

    if not WIFI_SSID:
        return False

    return True

def wlan_start():
    """Initialize and connect to WiFi network"""
    global wlan, ticks_start, connected, WIFI_PASSWORD, WIFI_SSID

    if not NETWORK_AVAILABLE:
        debug_log("Network not available")
        return False

    if ticks_start is None:
        ticks_start = io.ticks
        debug_log(f"Starting WiFi connection for SSID '{WIFI_SSID}'")

    if connected:
        return True

    if wlan is None:
        debug_log(f"Initializing WLAN interface")
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        if wlan.isconnected():
            connected = True
            debug_log("Already connected to WiFi")
            return True

    # attempt to find the SSID by scanning; some APs may be hidden intermittently
    try:
        ssid_found = False
        try:
            scans = wlan.scan()
            debug_log(f"Scanned {len(scans)} WiFi networks")
        except Exception as scan_err:
            debug_log(f"Scan failed: {scan_err}")
            scans = []

        for s in scans:
            # s[0] is SSID (bytes or str)
            ss = s[0]
            if isinstance(ss, (bytes, bytearray)):
                try:
                    ss = ss.decode("utf-8", "ignore")
                except Exception:
                    ss = str(ss)
            if ss == WIFI_SSID:
                ssid_found = True
                debug_log(f"Found target SSID '{WIFI_SSID}'")
                break

        if not ssid_found:
            elapsed = (io.ticks - ticks_start) / 1000.0
            debug_log(f"SSID not found (elapsed: {elapsed:.1f}s)")
            # not found yet; if still within timeout, keep trying on subsequent calls
            if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
                # return True to indicate we're still attempting to connect (in-progress)
                return True
            else:
                # timed out
                debug_log(f"WiFi scan timeout ({WIFI_TIMEOUT}s)")
                return False

        # SSID is visible; attempt to connect (or re-attempt)
        try:
            if not wlan.isconnected():
                debug_log(f"Connecting to '{WIFI_SSID}'")
                wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as conn_err:
            debug_log(f"Connect failed: {conn_err}")
            # connection initiation failed; we'll retry while still within timeout
            if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
                return True
            return False

        # update connected state
        connected = wlan.isconnected()

        # if connected, return True; otherwise indicate in-progress until timeout
        if connected:
            debug_log("WiFi connected!")
            return True
        if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
            elapsed = (io.ticks - ticks_start) / 1000.0
            debug_log(f"Connecting... ({elapsed:.1f}s)")
            return True
        debug_log(f"Connection timeout ({WIFI_TIMEOUT}s)")
        return False
    except Exception as e:
        # on unexpected errors, don't crash the UI; report and return False
        try:
            debug_log(f"wlan_start error: {e}")
        except Exception:
            # Ignore errors in error reporting to avoid crashing the UI
            pass
        return False

def parse_worldtime(data):
    """Parse WorldTimeAPI response format"""
    time_data = json.loads(data)
    datetime_str = time_data.get("datetime", "")
    if not datetime_str or "T" not in datetime_str:
        return None
    date_part = datetime_str.split("T")[0]
    parts = date_part.split("-")
    if len(parts) != 3:
        return None
    year, month, day = parts
    return (int(year), int(month), int(day))

def parse_timeapi(data):
    """Parse TimeAPI.io response format"""
    time_data = json.loads(data)
    year = time_data.get("year")
    month = time_data.get("month")
    day = time_data.get("day")
    if year and month and day:
        return (int(year), int(month), int(day))
    return None

def parse_aisense(data):
    """Parse AISENSE API response format"""
    time_data = json.loads(data)
    datetime_str = time_data.get("datetime", "")
    if not datetime_str or "T" not in datetime_str:
        return None
    # Format: "2025-10-30T01:23:45Z"
    date_part = datetime_str.split("T")[0]
    parts = date_part.split("-")
    if len(parts) != 3:
        return None
    year, month, day = parts
    return (int(year), int(month), int(day))

def parse_opentimezone(data):
    """Parse OpenTimezone API response format"""
    time_data = json.loads(data)
    datetime_str = time_data.get("datetime", "")
    if not datetime_str or "T" not in datetime_str:
        return None
    # Try alternate field names
    if not datetime_str:
        datetime_str = time_data.get("current_datetime", "")
    if not datetime_str or "T" not in datetime_str:
        return None
    date_part = datetime_str.split("T")[0]
    parts = date_part.split("-")
    if len(parts) != 3:
        return None
    year, month, day = parts
    return (int(year), int(month), int(day))

def fetch_current_date():
    """
    Fetch current date from multiple time APIs with fallback support
    Returns (year, month, day) tuple or None if all fetch attempts fail
    """
    global _cached_time, _last_fetch_attempt, _fetch_success, _last_error_type, _current_api_index
    
    if not NETWORK_AVAILABLE:
        debug_log("fetch_current_date: network not available")
        _last_error_type = "no_network"
        return None
    
    if not connected:
        debug_log("fetch_current_date: not connected to WiFi")
        _last_error_type = "no_wifi"
        return None
    
    # Return cached time if still valid
    current_ticks = io.ticks
    if _cached_time and _fetch_success and (current_ticks - _last_fetch_attempt < FETCH_INTERVAL):
        elapsed = (current_ticks - _last_fetch_attempt) / 1000.0
        debug_log(f"Using cached date (age: {elapsed:.1f}s)")
        return _cached_time
    
    # Check if we should retry (use shorter interval when failed)
    if not _fetch_success and _last_fetch_attempt > 0:
        wait_time = (current_ticks - _last_fetch_attempt) / 1000.0
        if current_ticks - _last_fetch_attempt < RETRY_INTERVAL:
            debug_log(f"Waiting to retry ({wait_time:.1f}s / {RETRY_INTERVAL/1000.0}s)")
            return None  # Return None to indicate we're still waiting to retry
    
    # Update last fetch attempt timestamp before trying
    _last_fetch_attempt = current_ticks
    
    # Try APIs in round-robin fashion for better load distribution
    num_apis = len(TIME_APIS)
    for attempt in range(num_apis):
        api_index = (_current_api_index + attempt) % num_apis
        url, parser_name = TIME_APIS[api_index]
        
        debug_log(f"Trying API {api_index+1}/{num_apis}: {url[:40]}...")
        
        try:
            # Reduced timeout to 3 seconds to keep badge responsive
            response = urlopen(url, timeout=3)
            try:
                data = response.read()
                debug_log(f"Received {len(data)} bytes from API {api_index+1}")
                
                # Get the appropriate parser function
                parser = globals().get(parser_name)
                if not parser:
                    debug_log(f"Parser {parser_name} not found")
                    continue
                
                # Parse the response
                result = parser(data)
                if result:
                    year, month, day = result
                    _cached_time = result
                    _fetch_success = True
                    _last_error_type = None
                    # Move to next API for next fetch to distribute load
                    _current_api_index = (api_index + 1) % num_apis
                    debug_log(f"Successfully parsed date from API {api_index+1}: {year}-{month}-{day}")
                    return _cached_time
                else:
                    debug_log(f"API {api_index+1} parser returned None")
            finally:
                response.close()
        except Exception as e:
            # This API failed, try the next one
            error_name = type(e).__name__
            debug_log(f"API {api_index+1} failed: {error_name}: {e}")
            # Continue to next API
    
    # All APIs failed
    debug_log("All time APIs failed")
    _fetch_success = False
    _last_error_type = "all_failed"
    # Move to next API for next attempt
    _current_api_index = (_current_api_index + 1) % num_apis
    
    return None

def format_date(year, month, day):
    """
    Format date as DD MMM YYYY (e.g., 30 Oct 2025)
    """
    month_name = MONTH_NAMES[month - 1] if 1 <= month <= 12 else "???"
    return f"{day:02d} {month_name} {year}"

def get_current_date_string():
    """
    Get current date formatted as DD MMM YYYY
    Returns formatted string or "thinking..." if date cannot be determined
    """
    # Try to fetch current date from internet
    fetched_date = fetch_current_date()
    
    if fetched_date:
        # Use internet time
        year, month, day = fetched_date
        return format_date(year, month, day)
    
    # Return "thinking..." if we don't have a date yet (no fallback to local time)
    return "thinking..."

def get_days_until_christmas():
    """
    Calculate days until next Christmas (Dec 25)
    Returns None if date cannot be determined from network
    """
    # Try to fetch current date from internet
    fetched_date = fetch_current_date()
    
    if not fetched_date:
        # Cannot calculate without valid date from network
        return None
    
    current_year, current_month, current_day = fetched_date
    
    # Determine which Christmas to count down to
    christmas_year = current_year
    if current_month == 12 and current_day > 25:
        # After Christmas, count to next year
        christmas_year += 1
    
    # Helper function to get days in month for a specific year
    def get_days_in_month(year):
        days = BASE_DAYS_IN_MONTH.copy()
        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        if is_leap:
            days[1] = 29
        return days
    
    # Calculate day of year for current date
    current_days_in_month = get_days_in_month(current_year)
    current_day_of_year = sum(current_days_in_month[:current_month-1]) + current_day
    
    # Calculate day of year for Christmas
    if christmas_year == current_year:
        # Christmas this year
        christmas_day_of_year = sum(current_days_in_month[:11]) + 25  # December 25
        days_left = christmas_day_of_year - current_day_of_year
    else:
        # Christmas next year
        days_left_this_year = sum(current_days_in_month) - current_day_of_year
        # Calculate days from Jan 1 to Christmas in next year
        next_year_days = get_days_in_month(christmas_year)
        days_jan1_to_christmas = sum(next_year_days[:11]) + 25  # Jan 1 to Dec 25
        days_left = days_left_this_year + days_jan1_to_christmas
    
    return max(0, days_left)

def update():
    global connected
    
    # Clear screen with dark blue background
    screen.brush = BG_BRUSH
    screen.clear()
    
    # Update and draw snowflakes (backdrop)
    for snowflake in snowflakes:
        snowflake.update()
        snowflake.draw()
    
    # Try to get connection details and start WLAN if network is available
    if NETWORK_AVAILABLE:
        if get_connection_details():
            wlan_start()
    
    # Calculate days until Christmas
    days = get_days_until_christmas()
    
    screen.font = large_font
    screen.brush = TEXT_BRUSH
    
    if days is not None:
        # We have a valid date - show countdown
        # Main number (at top)
        days_text = str(days)
        w, h = screen.measure_text(days_text)
        screen.text(days_text, 80 - (w // 2), 30)
        
        # Labels
        screen.font = small_font
        label = "days until"
        w, _ = screen.measure_text(label)
        screen.text(label, 80 - (w // 2), 60)
        
        label2 = "Christmas"
        w, _ = screen.measure_text(label2)
        screen.text(label2, 80 - (w // 2), 75)
    else:
        # Still fetching date - show appropriate message
        screen.font = small_font
        if not NETWORK_AVAILABLE:
            message = "network unavailable"
        elif not get_connection_details():
            message = "no wifi config"
        elif not connected:
            # Show connection progress
            if ticks_start:
                elapsed = (io.ticks - ticks_start) / 1000.0
                message = f"connecting {int(elapsed)}s"
            else:
                message = "connecting..."
        else:
            # Connected but no date yet - show fetch status
            if _last_fetch_attempt == 0:
                message = "fetching date..."
            elif not _fetch_success:
                # Show retry countdown or error
                wait_time = (io.ticks - _last_fetch_attempt) / 1000.0
                if wait_time < RETRY_INTERVAL / 1000.0:
                    retry_in = int((RETRY_INTERVAL / 1000.0) - wait_time)
                    if _last_error_type:
                        message = f"{_last_error_type} ({retry_in}s)"
                    else:
                        message = f"retry in {retry_in}s"
                else:
                    message = "fetching date..."
            else:
                message = "thinking..."
        w, _ = screen.measure_text(message)
        screen.text(message, 80 - (w // 2), 55)
        
        # Show debug log location at bottom
        screen.font = small_font
        debug_msg = f"log: {DEBUG_LOG_FILE}"
        w, _ = screen.measure_text(debug_msg)
        screen.text(debug_msg, 80 - (w // 2), 105)
    
    # Display today's date at the bottom (only if we have a real date, not "thinking...")
    date_string = get_current_date_string()
    if date_string and date_string != "thinking...":
        screen.font = small_font
        w, _ = screen.measure_text(date_string)
        screen.text(date_string, 80 - (w // 2), 105)

if __name__ == "__main__":
    # Clear previous log and start fresh
    try:
        with open(DEBUG_LOG_FILE, "w") as f:
            f.write("=== Christmas App Debug Log ===\n")
    except Exception:
        pass
    debug_log("App started")
    debug_log(f"Network available: {NETWORK_AVAILABLE}")
    run(update)
