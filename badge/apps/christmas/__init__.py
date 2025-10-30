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
FETCH_INTERVAL = 60 * 60 * 1000  # Try to fetch once per hour (in milliseconds) when successful
RETRY_INTERVAL = 5 * 1000  # Retry every 5 seconds (in milliseconds) when failed

# Network connection state
WIFI_TIMEOUT = 60
WIFI_PASSWORD = None
WIFI_SSID = None
wlan = None
connected = False
ticks_start = None

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
        print("DEBUG: Network not available")
        return False

    if ticks_start is None:
        ticks_start = io.ticks
        print(f"DEBUG: Starting WiFi connection process at tick {ticks_start}")

    if connected:
        return True

    if wlan is None:
        print(f"DEBUG: Initializing WLAN for SSID '{WIFI_SSID}'")
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        if wlan.isconnected():
            connected = True
            print("DEBUG: Already connected to WiFi")
            return True

    # attempt to find the SSID by scanning; some APs may be hidden intermittently
    try:
        ssid_found = False
        try:
            scans = wlan.scan()
            print(f"DEBUG: Found {len(scans)} WiFi networks")
        except Exception as scan_err:
            print(f"DEBUG: Scan failed: {scan_err}")
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
                print(f"DEBUG: Target SSID '{WIFI_SSID}' found in scan")
                break

        if not ssid_found:
            elapsed = (io.ticks - ticks_start) / 1000.0
            print(f"DEBUG: SSID '{WIFI_SSID}' not found after {elapsed:.1f}s")
            # not found yet; if still within timeout, keep trying on subsequent calls
            if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
                # return True to indicate we're still attempting to connect (in-progress)
                return True
            else:
                # timed out
                print(f"DEBUG: WiFi scan timeout after {WIFI_TIMEOUT}s")
                return False

        # SSID is visible; attempt to connect (or re-attempt)
        try:
            if not wlan.isconnected():
                print(f"DEBUG: Attempting to connect to '{WIFI_SSID}'")
                wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as conn_err:
            print(f"DEBUG: Connection attempt failed: {conn_err}")
            # connection initiation failed; we'll retry while still within timeout
            if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
                return True
            return False

        # update connected state
        connected = wlan.isconnected()

        # if connected, return True; otherwise indicate in-progress until timeout
        if connected:
            print("DEBUG: Successfully connected to WiFi!")
            return True
        if io.ticks - ticks_start < WIFI_TIMEOUT * 1000:
            elapsed = (io.ticks - ticks_start) / 1000.0
            print(f"DEBUG: Still connecting... ({elapsed:.1f}s elapsed)")
            return True
        print(f"DEBUG: Connection timeout after {WIFI_TIMEOUT}s")
        return False
    except Exception as e:
        # on unexpected errors, don't crash the UI; report and return False
        try:
            print("DEBUG: wlan_start error:", e)
        except Exception:
            # Ignore errors in error reporting to avoid crashing the UI
            pass
        return False

def fetch_current_date():
    """
    Fetch current date from worldtimeapi.org
    Returns (year, month, day) tuple or None if fetch fails
    """
    global _cached_time, _last_fetch_attempt, _fetch_success
    
    if not NETWORK_AVAILABLE:
        print("DEBUG: fetch_current_date - network not available")
        return None
    
    if not connected:
        print("DEBUG: fetch_current_date - not connected to WiFi")
        return None
    
    # Return cached time if still valid
    current_ticks = io.ticks
    if _cached_time and _fetch_success and (current_ticks - _last_fetch_attempt < FETCH_INTERVAL):
        elapsed = (current_ticks - _last_fetch_attempt) / 1000.0
        print(f"DEBUG: Using cached date (cached {elapsed:.1f}s ago)")
        return _cached_time
    
    # Check if we should retry (use shorter interval when failed)
    if not _fetch_success and _last_fetch_attempt > 0:
        wait_time = (current_ticks - _last_fetch_attempt) / 1000.0
        if current_ticks - _last_fetch_attempt < RETRY_INTERVAL:
            print(f"DEBUG: Waiting to retry API call ({wait_time:.1f}s / {RETRY_INTERVAL/1000.0}s)")
            return None  # Return None to indicate we're still waiting to retry
    
    # Update last fetch attempt timestamp before trying
    _last_fetch_attempt = current_ticks
    print("DEBUG: Attempting to fetch date from worldtimeapi.org...")
    
    # Attempt to fetch current date from the API
    try:
        # Use worldtimeapi.org - a free API that doesn't require authentication
        # Reduced timeout to 3 seconds to keep badge responsive
        response = urlopen("https://worldtimeapi.org/api/timezone/Etc/UTC", timeout=3)
        try:
            data = response.read()
            print(f"DEBUG: Received {len(data)} bytes from API")
            time_data = json.loads(data)
            # datetime format: "2025-10-30T01:23:45.123456+00:00"
            datetime_str = time_data.get("datetime", "")
            print(f"DEBUG: API datetime string: '{datetime_str}'")
            
            if datetime_str:
                # Parse the date part (YYYY-MM-DD) with validation
                try:
                    if "T" not in datetime_str:
                        raise ValueError("datetime string missing 'T' separator")
                    date_part = datetime_str.split("T")[0]
                    parts = date_part.split("-")
                    if len(parts) != 3:
                        raise ValueError("date part does not have three components")
                    year, month, day = parts
                    _cached_time = (int(year), int(month), int(day))
                    _fetch_success = True
                    print(f"DEBUG: Successfully parsed date: {year}-{month}-{day}")
                    return _cached_time
                except (ValueError, TypeError) as parse_err:
                    print(f"DEBUG: Failed to parse date from API response: {parse_err}")
                    _fetch_success = False
            else:
                print("DEBUG: API response missing datetime field")
                _fetch_success = False
        finally:
            response.close()
    except Exception as e:
        # Network request failed, will retry on next attempt
        print(f"DEBUG: Failed to fetch time from internet: {type(e).__name__}: {e}")
        _fetch_success = False
    
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
                # Show retry countdown
                wait_time = (io.ticks - _last_fetch_attempt) / 1000.0
                if wait_time < RETRY_INTERVAL / 1000.0:
                    retry_in = int((RETRY_INTERVAL / 1000.0) - wait_time)
                    message = f"retry in {retry_in}s"
                else:
                    message = "fetching date..."
            else:
                message = "thinking..."
        w, _ = screen.measure_text(message)
        screen.text(message, 80 - (w // 2), 55)
    
    # Display today's date at the bottom (only if we have a real date, not "thinking...")
    date_string = get_current_date_string()
    if date_string and date_string != "thinking...":
        screen.font = small_font
        w, _ = screen.measure_text(date_string)
        screen.text(date_string, 80 - (w // 2), 105)

if __name__ == "__main__":
    run(update)
