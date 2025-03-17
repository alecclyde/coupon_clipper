"""
Grocery Coupon Clipper - A tool to automatically clip digital coupons on grocery websites.
"""

import time
import random
import json
import logging
import os
import platform
import subprocess
import re
import psutil # type: ignore
from selenium import webdriver # type: ignore
from selenium.webdriver.chrome.options import Options # type: ignore
from selenium.webdriver.common.by import By # type: ignore
from selenium.webdriver.support.ui import WebDriverWait # type: ignore
from selenium.webdriver.support import expected_conditions as EC # type: ignore
from selenium.common.exceptions import ( # type: ignore
    TimeoutException, 
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from selenium.webdriver.common.action_chains import ActionChains # type: ignore
from selenium.webdriver.common.keys import Keys # type: ignore

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("coupon_clipper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CouponClipper")

class CouponClipper:
    """
    A class for automatically clipping coupons on grocery websites.
    """
    
    def __init__(self, config_file="coupon_config.json", attach_to_existing=True):
        """
        Initialize the CouponClipper with configuration and browser setup.
        
        Args:
            config_file (str): Path to the JSON configuration file
            attach_to_existing (bool): Whether to attach to an existing Chrome instance
        """
        self.config = self._load_config(config_file)
        self._use_default_profile = True  # Default to using the user's regular profile
        self.driver = None  # Will be initialized in setup_driver
        self.backoff_time = 1  # Initial backoff time in seconds
        self.consecutive_success = 0  # Track consecutive successful clips
        self.rate_limit_hit = False
        self.rate_limit_count = 0  # Count consecutive rate limit detections
        self.driver_options = None  # Store driver options for reconnection
        self.current_website_key = None  # Track current website for site-specific settings
        self.connection_attempt_count = 0  # Track connection attempts for recovery
        
    def _load_config(self, config_file):
        """Load configuration from a JSON file."""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_file} not found. Using default configuration.")
            return self._default_config()
            
    def _default_config(self):
        """Return a default configuration if no file is found."""
        return {
            "websites": {
                "foodlion": {
                    "url": "https://foodlion.com/savings/coupons/browse",
                    "coupon_button_selector": ".kds-Button--primary",
                    "coupon_clipped_indicator": ".kds-Button--secondary",
                    "load_more_button_selector": "button.kds-Load-More, button.load-more, button:contains('Load More')",
                    "captcha_indicators": [
                        "iframe[title*='recaptcha']",
                        "iframe[src*='recaptcha']",
                        "iframe[src*='captcha']",
                        "iframe[src*='cloudflare']"
                    ],
                    "rate_limit_indicators": [
                        "Too many requests",
                        "Please try again later"
                    ],
                    "site_specific_settings": {
                        "rapid_mode_compatible": False,
                        "min_delay_override": None,
                        "max_delay_override": None
                    }
                },
                "safeway": {
                    "url": "https://www.safeway.com/foru/coupons-deals.html",
                    "coupon_button_selector": "button.btn.btn-default.btn-block",
                    "coupon_clipped_indicator": "button.btn-tag-primary.disabled",
                    "load_more_button_selector": ".load-more-btn, button.load-more, #loadMoreButton",
                    "captcha_indicators": [
                        "iframe[title*='recaptcha']",
                        "iframe[src*='recaptcha']",
                        "iframe[src*='captcha']",
                        "iframe[src*='cloudflare']"
                    ],
                    "rate_limit_indicators": [
                        "Too many requests",
                        "Please try again later"
                    ],
                    "site_specific_settings": {
                        "rapid_mode_compatible": False,
                        "min_delay_override": None,
                        "max_delay_override": None
                    }
                },
                "weis": {
                    "url": "https://www.weismarkets.com/coupons/",
                    "coupon_button_selector": ".btn-load-more, .btn-clip, button.add-coupon, .coupon-btn:not(.added), .coupon-item__add, [data-testid='add-coupon']",
                    "coupon_clipped_indicator": ".btn-clip.added, .coupon-btn.added, .coupon-item__added, [data-testid='added-coupon']",
                    "load_more_button_selector": ".btn-load-more, .load-more-coupons, button:contains('Load More')",
                    "captcha_indicators": [
                        "iframe[title*='recaptcha']",
                        "iframe[src*='recaptcha']",
                        "iframe[src*='captcha']",
                        "iframe[src*='cloudflare']",
                        "#challenge-running",
                        "#challenge-form",
                        ".cf-browser-verification"
                    ],
                    "rate_limit_indicators": [
                        "You are being rate limited",  # More specific phrases that indicate actual rate limiting
                        "Too many requests in a short time",
                        "Rate limit exceeded"
                    ],
                    "site_specific_settings": {
                        "rapid_mode_compatible": False,
                        "min_delay_override": None,
                        "max_delay_override": None
                    }
                },
                "giant": {
                    "url": "https://giantfood.com/savings/coupons/browse/",
                    "coupon_button_selector": "button.coupon-clip-btn:not(.is-clipped)",
                    "coupon_clipped_indicator": "button.coupon-clip-btn.is-clipped",
                    "load_more_button_selector": ".load-more, #load-more, button.show-more, button:contains('Show More')",
                    "captcha_indicators": [
                        "iframe[title*='recaptcha']",
                        "iframe[src*='recaptcha']",
                        "iframe[src*='captcha']",
                        "iframe[src*='cloudflare']"
                    ],
                    "rate_limit_indicators": [
                        "Too many requests",
                        "Please try again later"
                    ],
                    "site_specific_settings": {
                        "rapid_mode_compatible": False,
                        "min_delay_override": None,
                        "max_delay_override": None
                    }
                },
                "harris_teeter": {
                    "url": "https://www.harristeeter.com/savings/cl/coupons/",
                    "coupon_button_selector": "button:contains('Clip'), button.kds-Button--primary:not([disabled]):not(:contains('Unclip')), button.kds-Button--primary[contains(text(), 'Clip')]",
                    "coupon_clipped_indicator": "button:contains('Unclip'), button.kds-Button--primary:contains('Unclip'), button.kds-Button--primary[disabled]",
                    "load_more_button_selector": "button.kds-Load-More, button.load-more, button:contains('Load More')",
                    "captcha_indicators": [
                        "iframe[title*='recaptcha']",
                        "iframe[src*='recaptcha']",
                        "iframe[src*='captcha']",
                        "iframe[src*='cloudflare']",
                        "div.g-recaptcha"
                    ],
                    "rate_limit_indicators": [
                        "Too many requests",
                        "Please try again later"
                    ],
                    "site_specific_settings": {
                        "rapid_mode_compatible": True,  # Harris Teeter can use rapid mode
                        "min_delay_override": 0.1,     # Much faster defaults for Harris Teeter
                        "max_delay_override": 0.3
                    }
                },
                "walmart": {
                    "url": "https://www.walmart.com/offer/all-offers",
                    "coupon_button_selector": "button:contains('Get this offer'), button.button--primary",
                    "coupon_clipped_indicator": "button:contains('Offer claimed'), button.button--primary[disabled]",
                    "load_more_button_selector": "button.load-more-button, button.show-more, button:contains('Load More')",
                    "captcha_indicators": [
                        "iframe[title*='recaptcha']",
                        "iframe[src*='recaptcha']",
                        "iframe[src*='captcha']",
                        "iframe[src*='cloudflare']",
                        "iframe[title*='Human verification challenge']"
                    ],
                    "rate_limit_indicators": [
                        "Too many requests",
                        "Please try again later"
                    ],
                    "site_specific_settings": {
                        "rapid_mode_compatible": False,
                        "min_delay_override": None,
                        "max_delay_override": None
                    }
                }
                # Add more websites as needed
            },
            "settings": {
                "max_retries": 5,
                "max_backoff_time": 30,  # Reduced maximum backoff time
                "random_delay_min": 0.5,  # Faster default delays
                "random_delay_max": 1.5,
                "scroll_pause_time": 0.8,  # Faster scroll pause
                "scroll_increment": 500,  # Larger increment for faster scrolling
                "load_more_max_attempts": 10,
                "slow_start": True,
                "acceleration_threshold": 3,
                "adaptive_delay": True,
                "enable_rate_limit_detection": True,  # Can be turned off
                "rate_limit_threshold": 3,  # Number of consecutive detections before considering it a true rate limit
                "rate_limit_check_main_content_only": True,  # Only check main content for rate limit messages
                "rate_limit_backoff_factor": 1.5,  # Less aggressive backoff factor (previously 2)
                "fast_scroll": True,  # Enable faster scrolling
                "enable_rapid_mode": False,  # New option for rapid clipping mode
                "max_recovery_attempts": 3,  # Maximum attempts to recover driver connection
                "connection_check_interval": 5,  # Check driver connection every N coupons
                "rapid_mode_min_delay": 0.05,  # Extra fast delays for rapid mode
                "rapid_mode_max_delay": 0.2
            }
        }
            
    def _find_chrome_path(self):
        """
        Find the Chrome executable path on different operating systems.
        
        Returns:
            str: Path to Chrome executable or None if not found
        """
        system = platform.system()
        possible_paths = []
        
        if system == "Windows":
            possible_paths = [
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Google\\Chrome\\Application\\chrome.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Google\\Chrome\\Application\\chrome.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google\\Chrome\\Application\\chrome.exe')
            ]
        elif system == "Darwin":  # macOS
            possible_paths = [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
            ]
        elif system == "Linux":
            possible_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/chrome',
                '/snap/bin/chromium',
                '/usr/bin/chromium',
                '/usr/bin/chromium-browser',
            ]
            
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found Chrome at: {path}")
                return path
                
        logger.warning("Could not find Chrome automatically.")
        return None
        
    def _get_chrome_default_profile(self):
        """
        Get the path to the default Chrome user data directory.
        
        Returns:
            str: Path to Chrome user data directory
        """
        system = platform.system()
        
        if system == "Windows":
            return os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google\\Chrome\\User Data')
        elif system == "Darwin":  # macOS
            return os.path.expanduser('~/Library/Application Support/Google/Chrome')
        elif system == "Linux":
            return os.path.expanduser('~/.config/google-chrome')
        
        return None
        
    def _get_chrome_profiles(self, user_data_dir):
        """
        Get a list of available Chrome profiles.
        
        Args:
            user_data_dir (str): Path to Chrome user data directory
            
        Returns:
            list: List of profile names
        """
        profiles = ["Default"]
        
        if not os.path.exists(user_data_dir):
            return profiles
            
        # Look for Profile* directories
        for item in os.listdir(user_data_dir):
            if item.startswith("Profile "):
                profiles.append(item)
                
        return profiles
    
    def _launch_chrome_with_debugging(self, port=9222, use_default_profile=True):
        """
        Launch Chrome with remote debugging enabled.
        
        Args:
            port (int): Debugging port to use
            use_default_profile (bool): Whether to use the default Chrome profile
            
        Returns:
            bool: True if Chrome was launched successfully, False otherwise
        """
        chrome_path = self._find_chrome_path()
        if not chrome_path:
            logger.error("Could not find Chrome to launch.")
            return False
            
        try:
            logger.info(f"Launching Chrome with remote debugging on port {port}")
            
            # Determine which profile to use
            user_data_dir = None
            profile_dir = None
            
            if use_default_profile:
                user_data_dir = self._get_chrome_default_profile()
                if user_data_dir and os.path.exists(user_data_dir):
                    logger.info(f"Using default Chrome profile at: {user_data_dir}")
                    
                    # Get available profiles
                    profiles = self._get_chrome_profiles(user_data_dir)
                    
                    if len(profiles) > 1:
                        print("\nAvailable Chrome profiles:")
                        for i, profile in enumerate(profiles, 1):
                            print(f"{i}. {profile}")
                            
                        try:
                            profile_idx = int(input("\nSelect profile number (or press Enter for Default): ") or "1") - 1
                            if 0 <= profile_idx < len(profiles):
                                profile_dir = profiles[profile_idx]
                            else:
                                profile_dir = "Default"
                        except ValueError:
                            profile_dir = "Default"
                    else:
                        profile_dir = "Default"
                    
                    logger.info(f"Using Chrome profile: {profile_dir}")
                else:
                    logger.warning("Could not find default Chrome profile directory")
                    user_data_dir = os.path.join(os.path.expanduser("~"), "ChromeDebugProfile")
                    os.makedirs(user_data_dir, exist_ok=True)
            else:
                user_data_dir = os.path.join(os.path.expanduser("~"), "ChromeDebugProfile")
                os.makedirs(user_data_dir, exist_ok=True)
            
            # Build the Chrome command
            cmd = [
                chrome_path,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={user_data_dir}"
            ]
            
            # Add profile directory if specified
            if profile_dir and profile_dir != "Default":
                cmd.append(f"--profile-directory={profile_dir}")
                
            cmd.extend([
                "--no-first-run",
                "--no-default-browser-check"
            ])
            
            # Check if Chrome is already running with this profile
            chrome_running = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    cmd_line = proc.info['cmdline']
                    if cmd_line and user_data_dir in ' '.join(cmd_line):
                        logger.warning("Chrome is already running with this profile")
                        chrome_running = True
                        break
            
            if not chrome_running:
                # Use Popen to avoid blocking
                process = subprocess.Popen(cmd)
                
                # Wait a bit for Chrome to start
                time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error launching Chrome: {e}")
            return False
            
    def setup_driver(self, attach_to_existing=True):
        """
        Set up the Chrome WebDriver, either attaching to an existing browser or creating a new one.
        
        Args:
            attach_to_existing (bool): Whether to attach to an existing Chrome browser
            
        Returns:
            webdriver.Chrome: Configured Chrome WebDriver instance
        """
        options = Options()
        
        if attach_to_existing:
            # Try to launch Chrome if requested
            self._launch_chrome_with_debugging(9222, self._use_default_profile)
            
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            logger.info("Attempting to attach to Chrome instance on 127.0.0.1:9222")
        else:
            # Regular Selenium setup for a new browser instance
            options.add_argument("--start-maximized")
            options.add_argument("--disable-notifications")
            # Reduce chance of being detected as automation
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Save options for potential reconnection
        self.driver_options = options
            
        try:
            self.driver = webdriver.Chrome(options=options)
            self.connection_attempt_count = 0  # Reset connection attempts on successful connection
            return self.driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def check_driver_connection(self):
        """
        Check if the WebDriver connection is still valid and try to reconnect if not.
        
        Returns:
            bool: True if connection is valid or reconnection successful, False otherwise
        """
        if not self.driver:
            return False
            
        try:
            # Try a simple operation to check connection
            _ = self.driver.current_url
            return True
        except Exception as e:
            logger.warning(f"Driver connection check failed: {e}")
            
            # Try to reconnect
            if self.connection_attempt_count < self.config["settings"].get("max_recovery_attempts", 3):
                self.connection_attempt_count += 1
                logger.info(f"Attempting to reconnect (attempt {self.connection_attempt_count})...")
                
                try:
                    # Close the broken driver if possible
                    try:
                        self.driver.quit()
                    except:
                        pass
                    
                    # Reset the driver
                    self.driver = None
                    
                    # Recreate the driver
                    time.sleep(2)  # Brief pause before reconnecting
                    self.driver = webdriver.Chrome(options=self.driver_options)
                    
                    # Try to navigate back to the current website
                    if self.current_website_key:
                        website_config = self.config["websites"][self.current_website_key]
                        self.driver.get(website_config['url'])
                        time.sleep(3)  # Wait for page to load
                    
                    logger.info("Successfully reconnected to browser")
                    return True
                except Exception as e:
                    logger.error(f"Failed to reconnect to browser: {e}")
                    return False
            else:
                logger.error(f"Exceeded maximum reconnection attempts ({self.connection_attempt_count})")
                return False
    
    def clip_coupons(self, website_key):
        """
        Main method to clip coupons for a specific website.
        Enhanced with improved detection, load more functionality and control via Ctrl+C.
        
        Args:
            website_key (str): Key for the website configuration in the config file
            
        Returns:
            bool: True if completed successfully, False if terminated early
        """
        if website_key not in self.config["websites"]:
            logger.error(f"Website '{website_key}' not found in configuration")
            return True  # Return True to continue with other websites
            
        # Store current website key for potential reconnection
        self.current_website_key = website_key
        
        website_config = self.config["websites"][website_key]
        settings = self.config["settings"]
        
        # Reset tracking variables
        self.backoff_time = 1
        self.consecutive_success = 0
        self.rate_limit_hit = False
        self.rate_limit_count = 0
        self.connection_attempt_count = 0
        
        # Apply site-specific settings if available
        site_settings = website_config.get("site_specific_settings", {})
        if site_settings:
            # Override delay settings if specified for this site
            if site_settings.get("min_delay_override") is not None:
                logger.info(f"Using site-specific min delay: {site_settings.get('min_delay_override')}")
                settings["site_min_delay"] = site_settings.get("min_delay_override")
            else:
                settings["site_min_delay"] = None
                
            if site_settings.get("max_delay_override") is not None:
                logger.info(f"Using site-specific max delay: {site_settings.get('max_delay_override')}")
                settings["site_max_delay"] = site_settings.get("max_delay_override")
            else:
                settings["site_max_delay"] = None
                
            # Check if site supports rapid mode
            settings["site_rapid_compatible"] = site_settings.get("rapid_mode_compatible", False)
            if settings["site_rapid_compatible"]:
                logger.info(f"{website_key} supports rapid mode for faster clipping")
        
        # Ask user if they want to enable rate limit detection for this site
        if website_key == "weis":
            print("\nWeis Markets may have issues with automatic rate limit detection.")
            print("1. Enable automatic rate limit detection (default)")
            print("2. Disable automatic rate limit detection")
            print("3. Manual mode - ask before applying rate limits")
            
            try:
                rate_limit_choice = input("\nSelect option (1-3, default: 1): ") or "1"
                
                if rate_limit_choice == "2":
                    settings["enable_rate_limit_detection"] = False
                    print("Automatic rate limit detection disabled.")
                elif rate_limit_choice == "3":
                    settings["manual_rate_limit_confirmation"] = True
                    print("Manual rate limit confirmation enabled.")
                else:
                    settings["enable_rate_limit_detection"] = True
                    settings["manual_rate_limit_confirmation"] = False
                    print("Automatic rate limit detection enabled.")
            except ValueError:
                # Default to enabling rate limit detection
                settings["enable_rate_limit_detection"] = True
                settings["manual_rate_limit_confirmation"] = False
        
        # Set up the driver if not already done
        if not self.driver:
            self.setup_driver()
        elif not self.check_driver_connection():
            # If driver connection check fails, try to set up a new driver
            logger.warning("Driver connection invalid, setting up new driver")
            self.setup_driver()
        
        try:
            # Navigate to the website
            logger.info(f"Navigating to {website_config['url']}")
            self.driver.get(website_config['url'])
            
            # Wait for the page to load
            time.sleep(settings.get("random_delay_max", 3))
            
            # Check for Cloudflare or other CAPTCHA
            if self._check_for_captcha(website_config):
                logger.info("Initial CAPTCHA handled")
            
            # Check for login requirement with improved detection
            if self._check_actual_login_required():
                print("\n" + "="*50)
                print("Login appears to be required. Please log in manually.")
                print("="*50)
                input("Press Enter after you've logged in to continue...")
                logger.info("User indicated login is complete, continuing")
                
                # Wait a bit more after login
                time.sleep(3)
                
            # Load all content by scrolling and clicking load more
            try:
                self._load_all_content(website_config, settings)
            except KeyboardInterrupt:
                # Allow the user to control the process during content loading
                choice = self._control_menu(0, 0)
                if choice != 'c':  # If not continue
                    return False
            
            # Try to find coupon buttons
            coupon_buttons = self._find_coupon_buttons_for_website(website_key, website_config)
            
            # If no buttons found, ask user to help
            if not coupon_buttons:
                coupon_buttons = self._ask_user_to_identify_button()
                if not coupon_buttons:
                    logger.info("No buttons identified, skipping website")
                    return True
            
            total_buttons = len(coupon_buttons)
            logger.info(f"Found {total_buttons} potential coupons to clip")
            
            # Show instructions for control
            print(f"\nFound {total_buttons} potential coupons to clip.")
            print("Clipping in progress...")
            print("Press Ctrl+C at any time to pause/control the process")
            
            # Ask for clip speed preference with site-specific options
            self._ask_clip_speed_preference(settings, website_key)
            
            # Clip coupons with adaptive delay and handling page changes
            clipped_count = 0
            already_clipped_count = 0
            i = 0
            buttons_updated = False
            
            # Pre-check all buttons for already clipped state to improve efficiency
            already_clipped_map = {}
            if settings.get("enable_rapid_mode", False) and settings.get("site_rapid_compatible", False):
                logger.info("Rapid mode enabled - pre-checking clipped status")
                for idx, button in enumerate(coupon_buttons):
                    try:
                        already_clipped_map[idx] = self._is_already_clipped(button, website_config)
                    except Exception:
                        # If we can't determine, assume not clipped
                        already_clipped_map[idx] = False
                
                already_clipped_count = sum(1 for clipped in already_clipped_map.values() if clipped)
                logger.info(f"Pre-check found {already_clipped_count} already clipped coupons")
            
            # Calculate initial delay based on settings and site-specific overrides
            min_delay = settings.get("site_min_delay") if settings.get("site_min_delay") is not None else settings.get("random_delay_min", 0.5)
            max_delay = settings.get("site_max_delay") if settings.get("site_max_delay") is not None else settings.get("random_delay_max", 1.5)
            
            # Apply rapid mode settings if enabled
            if settings.get("enable_rapid_mode", False) and settings.get("site_rapid_compatible", False):
                min_delay = settings.get("rapid_mode_min_delay", 0.05)
                max_delay = settings.get("rapid_mode_max_delay", 0.2)
                logger.info(f"Rapid mode active - using faster delays: {min_delay}-{max_delay}s")
            
            connection_check_counter = 0
            connection_check_interval = settings.get("connection_check_interval", 5)
            
            while i < len(coupon_buttons):
                try:
                    # Check connection periodically to ensure it's still valid
                    connection_check_counter += 1
                    if connection_check_counter >= connection_check_interval:
                        connection_check_counter = 0
                        if not self.check_driver_connection():
                            logger.warning("Lost connection to driver - attempting recovery")
                            
                            # If reconnection failed, ask user what to do
                            if not self.check_driver_connection():
                                print("\n" + "="*50)
                                print("ERROR: Lost connection to browser and couldn't reconnect.")
                                print("1. Try again")
                                print("2. Skip to next website")
                                print("3. Exit program")
                                print("="*50)
                                
                                try:
                                    reconnect_choice = input("Select option (1-3, default: 1): ") or "1"
                                    if reconnect_choice == "2":
                                        return True  # Skip to next website
                                    elif reconnect_choice == "3":
                                        self.close()
                                        exit(0)  # Exit program
                                    else:
                                        # Try one more time
                                        if not self.check_driver_connection():
                                            print("Reconnection failed. Skipping to next website.")
                                            return True
                                except Exception:
                                    return True  # On any error, move to next website
                            
                            # If we reconnected successfully, re-find buttons
                            print("Successfully reconnected to browser. Re-finding coupon buttons...")
                            coupon_buttons = self._find_coupon_buttons_for_website(website_key, website_config)
                            if not coupon_buttons:
                                print("Could not find coupon buttons after reconnection. Skipping website.")
                                return True
                            
                            i = 0  # Reset counter
                            already_clipped_count = 0
                            clipped_count = 0
                            buttons_updated = False
                            continue
                    
                    # Each time we try to access a button, first check if we need to refresh our button list
                    if buttons_updated:
                        buttons_updated = False
                        # If we detect the page has changed, update our button list
                        try:
                            new_buttons = self._find_coupon_buttons_for_website(website_key, website_config)
                                
                            if new_buttons:
                                logger.info(f"Found {len(new_buttons)} buttons after page update")
                                coupon_buttons = new_buttons
                                total_buttons = len(coupon_buttons)
                                # Reset index to start from beginning with new buttons
                                i = 0
                                already_clipped_count = 0
                                # Continue with the loop
                                continue
                        except Exception as e:
                            logger.warning(f"Error updating buttons after page change: {e}")
                            
                    # If we've gone through all buttons, we're done
                    if i >= len(coupon_buttons):
                        break
                        
                    button = coupon_buttons[i]
                    
                    # Check if button is already clipped before attempting
                    already_clipped = False
                    try:
                        # If using rapid mode, use our pre-checked map
                        if settings.get("enable_rapid_mode", False) and settings.get("site_rapid_compatible", False):
                            if i in already_clipped_map:
                                already_clipped = already_clipped_map[i]
                            else:
                                already_clipped = self._is_already_clipped(button, website_config)
                        else:
                            # Standard check for each button
                            already_clipped = self._is_already_clipped(button, website_config)
                        
                        if already_clipped:
                            already_clipped_count += 1
                            i += 1
                            continue
                    except StaleElementReferenceException:
                        # If button is stale, we need to refresh our button list
                        logger.info("Detected stale element, refreshing button list")
                        buttons_updated = True
                        continue
                    
                    # Determine current delay based on consecutive successes
                    current_min_delay = min_delay
                    current_max_delay = max_delay
                    
                    # If slow start is enabled, adapt delay based on consecutive successes
                    if settings.get("slow_start", True) and not settings.get("enable_rapid_mode", False):
                        if self.consecutive_success < settings.get("acceleration_threshold", 3):
                            # Start slower
                            current_min_delay = max(min_delay, min_delay * 1.5)
                            current_max_delay = max(max_delay, max_delay * 1.5)
                        elif self.rate_limit_hit:
                            # If we've hit rate limits, be more cautious
                            current_min_delay = max(min_delay, min_delay * 1.2)
                            current_max_delay = max(max_delay, max_delay * 1.2)
                        else:
                            # We've had several consecutive successes, go faster
                            current_min_delay = min_delay
                            current_max_delay = max_delay
                    
                    # Add delay before clicking
                    time.sleep(random.uniform(current_min_delay, current_max_delay))
                    
                    success = False
                    
                    # Use the appropriate clicking strategy based on the website
                    if website_key in ["weis", "harris_teeter"]:
                        try:
                            success = self._enhanced_click_button(button)
                        except StaleElementReferenceException:
                            # Button became stale, refresh our list
                            logger.info("Button became stale during click, refreshing list")
                            buttons_updated = True
                            continue
                        except Exception as e:
                            logger.warning(f"Error with enhanced button click: {e}")
                    else:
                        # Standard clicking for other sites
                        try:
                            success = self._click_button(button)
                        except StaleElementReferenceException:
                            # Button became stale, refresh our list
                            logger.info("Button became stale during click, refreshing list")
                            buttons_updated = True
                            continue
                        except Exception as e:
                            logger.warning(f"Error clicking button: {e}")
                    
                    if success:
                        clipped_count += 1
                        self.consecutive_success += 1
                        
                        # In rapid mode, we only show progress periodically to reduce overhead
                        if settings.get("enable_rapid_mode", False):
                            if clipped_count % 5 == 0 or clipped_count == 1:
                                logger.info(f"Clipped coupon ({clipped_count}/{total_buttons - already_clipped_count} unclipped) - consecutive: {self.consecutive_success}")
                        else:
                            logger.info(f"Clipped coupon ({clipped_count}/{total_buttons - already_clipped_count} unclipped) - consecutive: {self.consecutive_success}")
                        
                        # Check for rate limiting - with improved detection
                        # Skip rate limit checks in rapid mode to improve speed unless explicitly forced
                        check_rate_limits = (not settings.get("enable_rapid_mode", False)) or settings.get("force_rate_limit_checks", False)
                        
                        rate_limited = False
                        if check_rate_limits and settings.get("enable_rate_limit_detection", True):
                            rate_limited = self._is_rate_limited(website_config, settings)
                            
                            if rate_limited and settings.get("manual_rate_limit_confirmation", False):
                                # Ask user to confirm if we're actually rate limited
                                print("\n" + "="*50)
                                print("Potential rate limiting detected.")
                                print("1. Yes, we're being rate limited - back off and try later")
                                print("2. No, continue clipping (ignore the detection)")
                                print("3. No, and disable automatic detection")
                                print("="*50)
                                
                                try:
                                    confirm = input("Select option (1-3, default: 1): ") or "1"
                                    if confirm == "2":
                                        rate_limited = False
                                    elif confirm == "3":
                                        rate_limited = False
                                        settings["enable_rate_limit_detection"] = False
                                        print("Automatic rate limit detection disabled for this session.")
                                except KeyboardInterrupt:
                                    # If user presses Ctrl+C during input, assume they want to pause
                                    choice = self._control_menu(clipped_count, total_buttons - i - already_clipped_count)
                                    if choice != 'c':  # If not continue
                                        return choice == 's'  # Return True if "s" (select new site), False otherwise
                        
                        if rate_limited:
                            self.rate_limit_hit = True
                            self.consecutive_success = 0
                            buttons_updated = self._handle_rate_limit(settings)
                            continue  # Skip incrementing index, as buttons list might have changed
                            
                        # Check for CAPTCHA if not in rapid mode (to reduce overhead)
                        if not settings.get("enable_rapid_mode", False) and self._check_for_captcha(website_config):
                            logger.info("CAPTCHA encountered and handled")
                            buttons_updated = True
                            continue  # Skip incrementing index, as buttons list might have changed
                            
                        # Check if the page structure changes after clipping (especially for sites that remove clipped coupons)
                        # Skip this check in rapid mode for compatible sites
                        if not (settings.get("enable_rapid_mode", False) and settings.get("site_rapid_compatible", False)):
                            try:
                                # Quick check to see if button is still valid
                                button.is_displayed()
                            except StaleElementReferenceException:
                                # Button is now stale, likely page updated
                                logger.info("Page structure changed after clip, refreshing buttons")
                                buttons_updated = True
                                continue
                    else:
                        # If click failed, reset consecutive success counter
                        self.consecutive_success = 0
                        logger.warning(f"Failed to clip coupon at index {i}")
                    
                    # Move to next button
                    i += 1
                            
                except KeyboardInterrupt:
                    # Show control menu when user presses Ctrl+C
                    choice = self._control_menu(clipped_count, total_buttons - i - already_clipped_count)
                    if choice == 'q':  # Quit this website
                        return False
                    elif choice == 's':  # Return to website selection
                        return True
                    elif choice == 'r':  # Reconnect to browser
                        logger.info("User requested browser reconnection")
                        
                        if self.check_driver_connection():
                            print("Connection already valid - continuing")
                        else:
                            # Try to reconnect
                            print("Attempting to reconnect to browser...")
                            if self.check_driver_connection():
                                print("Successfully reconnected to browser.")
                                
                                # Re-find buttons
                                coupon_buttons = self._find_coupon_buttons_for_website(website_key, website_config)
                                if not coupon_buttons:
                                    print("Could not find coupon buttons after reconnection. Skipping website.")
                                    return True
                                    
                                i = 0  # Reset counter
                                already_clipped_count = 0
                                clipped_count = 0
                                buttons_updated = False
                            else:
                                print("Failed to reconnect. Skipping to next website.")
                                return True
                    # If 'c', we just continue the loop
                except Exception as e:
                    logger.warning(f"Error during coupon clipping: {e}")
                    # If we get an error, move to the next button but reset consecutive success
                    self.consecutive_success = 0
                    i += 1
                    
            logger.info(f"Finished clipping coupons for {website_key}. Clipped {clipped_count} coupons.")
            return True
            
        except KeyboardInterrupt:
            # Catch Ctrl+C at the outer level too
            choice = self._control_menu(
                clipped_count if 'clipped_count' in locals() else 0, 
                (total_buttons - i - already_clipped_count) if 'i' in locals() and 'total_buttons' in locals() and 'already_clipped_count' in locals() else 0
            )
            if choice == 'q':  # Quit this website
                return False
            elif choice == 's':  # Return to website selection
                return True
            else:
                return True  # Continue with other websites
            
        except Exception as e:
            logger.error(f"Error while clipping coupons: {e}")
            print(f"\nAn error occurred: {e}")
            choice = input("\nContinue to next website? (y/n, default: y): ").lower() or 'y'
            return choice != 'n'  # Return True to continue with other websites unless user says no
    
    def _ask_clip_speed_preference(self, settings, website_key=None):
        """
        Ask the user for their preferred clipping speed with site-specific options.
        
        Args:
            settings (dict): Settings dictionary to update
            website_key (str): Current website key for site-specific options
        """
        print("\nSelect clipping speed:")
        
        # Check if this site supports rapid mode
        site_specific_options = ""
        if website_key and settings.get("site_rapid_compatible", False):
            site_specific_options = f"\n5. Ultra Fast (Rapid Mode - optimized for {website_key})"

        print("1. Slow (safe, fewer rate limits)")
        print("2. Medium (balanced)")
        print("3. Fast (aggressive, may hit rate limits)")
        print("4. Custom (specify your own timing)" + site_specific_options)
        
        try:
            max_option = 5 if site_specific_options else 4
            speed_choice = input(f"Select option (1-{max_option}, default: 2): ") or "2"
            
            # Reset rapid mode flag
            settings["enable_rapid_mode"] = False
            
            if speed_choice == "1":
                # Slow
                settings["random_delay_min"] = 1.5
                settings["random_delay_max"] = 3.0
                print("Slow clipping speed selected.")
            elif speed_choice == "3":
                # Fast
                settings["random_delay_min"] = 0.1
                settings["random_delay_max"] = 0.5
                print("Fast clipping speed selected.")
            elif speed_choice == "4":
                # Custom
                try:
                    min_delay = float(input("Enter minimum delay in seconds (default: 0.5): ") or "0.5")
                    max_delay = float(input("Enter maximum delay in seconds (default: 1.5): ") or "1.5")
                    settings["random_delay_min"] = max(0.1, min_delay)  # Ensure minimum of 0.1s
                    settings["random_delay_max"] = max(settings["random_delay_min"], max_delay)
                    print(f"Custom timing set: {settings['random_delay_min']}-{settings['random_delay_max']} seconds.")
                except ValueError:
                    print("Invalid input, using default medium speed.")
                    settings["random_delay_min"] = 0.5
                    settings["random_delay_max"] = 1.5
            elif speed_choice == "5" and site_specific_options:
                # Rapid Mode for compatible sites
                settings["enable_rapid_mode"] = True
                settings["random_delay_min"] = settings.get("rapid_mode_min_delay", 0.05)
                settings["random_delay_max"] = settings.get("rapid_mode_max_delay", 0.2)
                print(f"Rapid mode enabled! Using ultra-fast timings optimized for {website_key}.")
                print("This mode skips certain checks for maximum speed.")
            else:
                # Medium (default)
                settings["random_delay_min"] = 0.5
                settings["random_delay_max"] = 1.5
                print("Medium clipping speed selected.")
                
            # Apply site-specific overrides if available and not using custom/rapid mode
            if website_key and speed_choice not in ["4", "5"]:
                site_settings = self.config["websites"][website_key].get("site_specific_settings", {})
                if site_settings.get("min_delay_override") is not None:
                    settings["random_delay_min"] = site_settings.get("min_delay_override")
                    print(f"Applied {website_key}-specific minimum delay: {settings['random_delay_min']}s")
                    
                if site_settings.get("max_delay_override") is not None:
                    settings["random_delay_max"] = site_settings.get("max_delay_override")
                    print(f"Applied {website_key}-specific maximum delay: {settings['random_delay_max']}s")
                
        except Exception:
            # Use default values if any error occurs
            settings["random_delay_min"] = 0.5
            settings["random_delay_max"] = 1.5
    
    def _find_coupon_buttons_for_website(self, website_key, website_config):
        """
        Find coupon buttons using the best strategy for each website.
        
        Args:
            website_key (str): The website key
            website_config (dict): Website configuration
            
        Returns:
            list: List of WebElement buttons
        """
        if website_key == "weis":
            # For Weis, try the specialized approach first
            buttons = self._find_weis_buttons_directly()
            if buttons:
                return buttons
                
            # Also try finding by text, especially "CLIP COUPON" for Weis
            clip_buttons = self._find_buttons_by_text("CLIP COUPON")
            if clip_buttons:
                logger.info(f"Found {len(clip_buttons)} buttons with text 'CLIP COUPON'")
                return clip_buttons
                
        elif website_key == "harris_teeter":
            # For Harris Teeter, specifically look for "Clip" buttons
            clip_buttons = self._find_buttons_by_text("Clip")
            if clip_buttons:
                # Filter out any that say "Unclip" - these are already clipped coupons
                filtered_buttons = []
                for button in clip_buttons:
                    try:
                        if "unclip" not in button.text.lower():
                            filtered_buttons.append(button)
                    except Exception:
                        pass
                        
                if filtered_buttons:
                    logger.info(f"Found {len(filtered_buttons)} 'Clip' buttons (excluding 'Unclip')")
                    return filtered_buttons
        
        # For other sites or as fallback, use standard detection
        return self._find_coupon_buttons(website_config)
    
    def _find_buttons_by_text(self, button_text):
        """
        Find buttons by their text content.
        
        Args:
            button_text (str): The text to look for
            
        Returns:
            list: List of WebElement buttons
        """
        try:
            # First try exact text (case-sensitive)
            xpath = f"//*[text()='{button_text}']"
            buttons = self.driver.find_elements(By.XPATH, xpath)
            
            if not buttons:
                # Try case-insensitive match
                xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{button_text.lower()}')]"
                buttons = self.driver.find_elements(By.XPATH, xpath)
                
            return buttons
        except Exception as e:
            logger.warning(f"Error finding buttons by text: {e}")
            return []
    
    def _load_all_content(self, website_config, settings):
        """
        Enhanced method to load all content by clicking 'load more' buttons and scrolling.
        Added safeguards against infinite loops.
        
        Args:
            website_config (dict): Website configuration
            settings (dict): General settings
        """
        logger.info("Loading all content...")
        
        # Track the number of load more attempts
        load_more_attempts = 0
        max_attempts = settings.get("load_more_max_attempts", 10)
        
        # Initial wait for the page to load any dynamic content
        time.sleep(3)
        
        # Limit the number of attempts to avoid infinite loops
        max_iterations = 5  # Set a hard limit on the number of load/scroll cycles
        iterations = 0
        
        # Keep clicking load more and scrolling until we can't anymore
        content_changed = True
        previous_page_source_length = len(self.driver.page_source)
        
        while content_changed and load_more_attempts < max_attempts and iterations < max_iterations:
            iterations += 1
            logger.info(f"Content loading iteration {iterations}/{max_iterations}")
            
            # Scroll through the page to reveal any lazy-loaded content or buttons
            self._scroll_to_load_all(settings)
            
            # Try to find and click a load more button
            load_more_button_clicked = False
            
            try:
                # Try to click a load more button
                if self._click_load_more_button(website_config):
                    load_more_attempts += 1
                    load_more_button_clicked = True
                    logger.info(f"Clicked 'load more' button ({load_more_attempts}/{max_attempts})")
                    
                    # Give extra time for content to load
                    time.sleep(3)
                
                # Check if the page content has changed significantly
                current_length = len(self.driver.page_source)
                content_growth = current_length - previous_page_source_length
                
                logger.info(f"Content size change: {content_growth} bytes")
                
                # If we clicked a button but content didn't grow much, we may be done
                if load_more_button_clicked and content_growth < 500:
                    logger.info("Clicked load more but content didn't change significantly")
                    # One more attempt to scroll and check
                    self._scroll_to_load_all(settings)
                    current_length = len(self.driver.page_source)
                    if current_length - previous_page_source_length < 500:
                        logger.info("Confirmed no significant content change, all content may be loaded")
                        content_changed = False
                    else:
                        previous_page_source_length = current_length
                elif content_growth > 500:
                    # Content changed significantly, continue loading
                    logger.info(f"Content grew by {content_growth} bytes")
                    previous_page_source_length = current_length
                    content_changed = True
                else:
                    # Content didn't change and no button was clicked, we're probably done
                    if not load_more_button_clicked:
                        logger.info("No more 'load more' buttons found and content unchanged")
                        content_changed = False
                        
            except Exception as e:
                logger.warning(f"Error in content loading process: {e}")
                iterations += 1  # Increment to avoid getting stuck
                
            # Safety check - if we're seeing minimal changes after multiple iterations, stop
            if iterations > 2 and content_growth < 1000:
                logger.info("Minimal content growth after multiple attempts, ending content loading")
                break
                
        if load_more_attempts >= max_attempts:
            logger.info(f"Reached maximum number of 'load more' attempts ({max_attempts})")
        elif iterations >= max_iterations:
            logger.info(f"Reached maximum number of content loading iterations ({max_iterations})")
        
        # One final complete page scroll to ensure everything is loaded
        self._scroll_to_load_all(settings)
        
        logger.info("Finished loading all content")
    
    def _scroll_to_load_all(self, settings):
        """
        Scroll down the page to load all dynamic content with improved stopping conditions.
        """
        logger.info("Scrolling to load all coupons...")
        
        # Get scroll height
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        # Add a maximum number of scroll attempts to prevent infinite loops
        max_scroll_attempts = 3
        scroll_attempts = 0
        
        # Use faster scrolling if enabled
        if settings.get("fast_scroll", True):
            # Faster scrolling with fewer increments
            while scroll_attempts < max_scroll_attempts:
                scroll_attempts += 1
                
                # Scroll down in fewer larger jumps
                for i in range(0, last_height, settings.get("scroll_increment", 500)):
                    self.driver.execute_script(f"window.scrollTo(0, {i});")
                    # Very brief pause between jumps
                    time.sleep(0.2)  
                
                # Brief pause at the bottom
                time.sleep(settings.get("scroll_pause_time", 0.8))
                
                # Calculate new scroll height and compare with last scroll height
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logger.info(f"Page height unchanged after scroll attempt {scroll_attempts}, finished scrolling")
                    break
                    
                logger.info(f"Page height changed from {last_height} to {new_height} on scroll attempt {scroll_attempts}/{max_scroll_attempts}")
                last_height = new_height
        else:
            # Original slower scrolling method
            while scroll_attempts < max_scroll_attempts:
                scroll_attempts += 1
                
                # Scroll down by increments
                for i in range(0, last_height, settings.get("scroll_increment", 300)):
                    self.driver.execute_script(f"window.scrollTo(0, {i});")
                    time.sleep(settings.get("scroll_pause_time", 1.5) / 3)
                    
                # Wait to load page
                time.sleep(settings.get("scroll_pause_time", 1.5))
                
                # Calculate new scroll height and compare with last scroll height
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logger.info(f"Page height unchanged after scroll attempt {scroll_attempts}, finished scrolling")
                    break
                    
                logger.info(f"Page height changed from {last_height} to {new_height} on scroll attempt {scroll_attempts}/{max_scroll_attempts}")
                last_height = new_height
            
        # Scroll back to top
        self.driver.execute_script("window.scrollTo(0, 0);")
        logger.info("Finished scrolling")
    
    def _check_for_captcha(self, website_config):
        """
        Improved CAPTCHA detection that checks for CloudFlare and other CAPTCHAs.
        
        Returns:
            bool: True if CAPTCHA was detected and handled, False otherwise
        """
        try:
            # Check for specific CAPTCHA elements (more reliable)
            captcha_detected = False
            
            # Check for CloudFlare CAPTCHA specifically
            cloudflare_indicators = [
                "#challenge-running",
                "#challenge-form",
                ".cf-browser-verification",
                "#cf-please-wait",
                "#cf-content"
            ]
            
            for indicator in cloudflare_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements and any(e.is_displayed() for e in elements):
                        captcha_detected = True
                        logger.info(f"CloudFlare CAPTCHA detected via element: {indicator}")
                        break
                except Exception:
                    pass
            
            # Look for reCAPTCHA iframes
            if not captcha_detected:
                for indicator in website_config.get("captcha_indicators", []):
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                        if elements and any(e.is_displayed() for e in elements):
                            captcha_detected = True
                            logger.info(f"CAPTCHA detected via element: {indicator}")
                            break
                    except Exception:
                        pass
            
            # Look for specific CAPTCHA UI elements
            if not captcha_detected:
                captcha_selectors = [
                    ".g-recaptcha",
                    "#captcha",
                    "[name='captcha']",
                    "[id*='captcha']",
                    "[class*='captcha']",
                    ".recaptcha-checkbox"
                ]
                
                for selector in captcha_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements and any(e.is_displayed() for e in elements):
                            captcha_detected = True
                            logger.info(f"CAPTCHA detected via selector: {selector}")
                            break
                    except Exception:
                        pass
            
            # Check for explicit CAPTCHA phrases
            if not captcha_detected:
                # Get text from the main content body only
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    captcha_phrases = [
                        "complete the captcha",
                        "solve the captcha",
                        "i'm not a robot",
                        "security check",
                        "checking your browser",
                        "please enable javascript",
                        "please wait while we verify",
                        "please wait..." # CloudFlare indicator
                    ]
                    
                    for phrase in captcha_phrases:
                        if phrase in body_text:
                            # Only if the phrase is prominent (not in footer or hidden)
                            captcha_detected = True
                            logger.info(f"CAPTCHA detected via text phrase: '{phrase}'")
                            break
                except Exception:
                    pass
            
            if not captcha_detected:
                return False
                
            logger.info("CAPTCHA detected")
            
            # For CloudFlare CAPTCHA, just wait longer
            if any(self.driver.find_elements(By.CSS_SELECTOR, indicator) for indicator in cloudflare_indicators):
                print("\n" + "="*50)
                print("CloudFlare security check detected. Waiting for completion...")
                print("If prompted, please complete any verification manually.")
                print("="*50)
                
                # Wait longer for CloudFlare to resolve automatically
                time.sleep(10)
                
                # Check if CloudFlare is still active
                if any(self.driver.find_elements(By.CSS_SELECTOR, indicator) for indicator in cloudflare_indicators):
                    self._user_solve_captcha()
                    return True
                else:
                    logger.info("CloudFlare check completed automatically")
                    return True
            
            # For other CAPTCHAs, try refreshing first
            logger.info("Attempting to refresh the page to bypass CAPTCHA")
            self.driver.refresh()
            time.sleep(5)  # Wait for page to reload
            
            # Check if CAPTCHA is still there after refresh
            if any(any(self.driver.find_elements(By.CSS_SELECTOR, indicator)) for indicator in captcha_selectors + website_config.get("captcha_indicators", [])):
                logger.info("CAPTCHA persists after refresh, handing off to user")
                self._user_solve_captcha()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in CAPTCHA detection: {e}")
            return False
    
    def _user_solve_captcha(self):
        """
        Prompt the user to solve the CAPTCHA manually.
        """
        print("\n" + "="*50)
        print("CAPTCHA detected! Please solve it manually in the browser.")
        print("="*50)
        
        input("Press Enter when you've solved the CAPTCHA to continue...")
        logger.info("User indicated CAPTCHA has been solved, continuing")
    
    def _check_actual_login_required(self):
        """
        Improved login detection that checks if login is actually required and prominent,
        not just mentioned somewhere on the page.
        
        Returns:
            bool: True if login appears to be required, False otherwise
        """
        try:
            # Check for login forms that are visible and in prominent positions
            login_form_indicators = [
                "form[action*='login']",
                "form[action*='signin']",
                "form.login-form",
                "#login-form",
                ".login-form",
                "form.signin-form",
                "#signin-form",
                ".signin-form"
            ]
            
            for indicator in login_form_indicators:
                try:
                    forms = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if forms and any(form.is_displayed() for form in forms):
                        # Check if the form is in a prominent position
                        for form in forms:
                            if form.is_displayed():
                                # Check position relative to viewport
                                position = self.driver.execute_script("""
                                    var rect = arguments[0].getBoundingClientRect();
                                    return {
                                        top: rect.top,
                                        left: rect.left,
                                        width: rect.width,
                                        height: rect.height,
                                        windowHeight: window.innerHeight,
                                        windowWidth: window.innerWidth
                                    };
                                """, form)
                                
                                # If form is prominent (in the upper half of the screen and reasonably sized)
                                if (position['top'] < position['windowHeight'] / 2 and 
                                    position['width'] > 200 and position['height'] > 100):
                                    logger.info(f"Login form detected in prominent position: {indicator}")
                                    return True
                except Exception:
                    pass
            
            # Check for visible login buttons/links in main content areas
            login_button_indicators = [
                "button:contains('Sign In')",
                "button:contains('Log In')",
                "a:contains('Sign In')",
                "a:contains('Log In')"
            ]
            
            for xpath in login_button_indicators:
                try:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    if elements:
                        for element in elements:
                            if element.is_displayed():
                                # Check position
                                position = self.driver.execute_script("""
                                    var rect = arguments[0].getBoundingClientRect();
                                    return {
                                        top: rect.top,
                                        isMainContent: rect.top < window.innerHeight / 2
                                    };
                                """, element)
                                
                                if position['isMainContent']:
                                    logger.info(f"Login button detected in main content: {xpath}")
                                    return True
                except Exception:
                    pass
            
            # Check for clear login messaging in main content
            main_content_selectors = ["main", "#main", ".main-content", "#content", ".content"]
            login_phrases = [
                "please log in to view coupons",
                "please sign in to view coupons",
                "login required to see coupons",
                "sign in required to see coupons",
                "log in to clip coupons",
                "sign in to clip coupons"
            ]
            
            for selector in main_content_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            element_text = element.text.lower()
                            if any(phrase in element_text for phrase in login_phrases):
                                logger.info(f"Login message found in main content: {selector}")
                                return True
                except Exception:
                    pass
            
            return False
            
        except Exception as e:
            logger.error(f"Error in login detection: {e}")
            return False
            
    def _click_load_more_button(self, website_config):
        """
        Find and click a 'load more' button if present.
        
        Args:
            website_config (dict): Website configuration
            
        Returns:
            bool: True if a button was found and clicked, False otherwise
        """
        if "load_more_button_selector" not in website_config:
            return False
            
        selector = website_config["load_more_button_selector"]
        try:
            # First try the provided CSS selector
            buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
            
            # If no buttons found, try text-based search
            if not buttons:
                for text in ["load more", "show more", "view more", "more coupons", "see more"]:
                    xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
                    text_buttons = self.driver.find_elements(By.XPATH, xpath)
                    if text_buttons:
                        buttons = text_buttons
                        break
            
            # If still no buttons, try common attribute-based selectors
            if not buttons:
                attribute_selectors = [
                    "[id*='load-more']", 
                    "[id*='loadMore']", 
                    "[class*='load-more']", 
                    "[class*='loadMore']"
                ]
                
                for attr_selector in attribute_selectors:
                    attr_buttons = self.driver.find_elements(By.CSS_SELECTOR, attr_selector)
                    if attr_buttons:
                        buttons = attr_buttons
                        break
            
            # Try to find a visible and clickable button
            for button in buttons:
                try:
                    if button.is_displayed() and (button.tag_name != "button" or button.is_enabled()):
                        # Scroll to center the button
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                        time.sleep(0.5)
                        
                        # Try multiple approaches to click
                        try:
                            # Try a regular click
                            button.click()
                        except Exception:
                            # Try JS click if regular click fails
                            self.driver.execute_script("arguments[0].click();", button)
                        
                        return True
                except Exception:
                    pass
            
            return False
            
        except Exception as e:
            logger.debug(f"Error in load more button detection: {e}")
            return False
    
    def _find_coupon_buttons(self, website_config):
        """
        Find all coupon clip buttons on the page.
        """
        all_buttons = []
        logger.info("Searching for coupon buttons with multiple strategies...")
        
        try:
            # Try direct CSS selector approach first
            if "coupon_button_selector" in website_config:
                selectors = website_config["coupon_button_selector"].split(", ")
                for selector in selectors:
                    try:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if buttons:
                            logger.info(f"Found {len(buttons)} buttons with selector: {selector}")
                            all_buttons.extend(buttons)
                    except Exception:
                        pass
            
            # Try text-based search for common button text
            button_texts = ["clip coupon", "CLIP COUPON", "clip", "add coupon", "add offer"]
            for text in button_texts:
                try:
                    # Try with exact text match
                    xpath = f"//*[text()='{text}']"
                    text_buttons = self.driver.find_elements(By.XPATH, xpath)
                    if text_buttons:
                        logger.info(f"Found {len(text_buttons)} buttons with exact text: '{text}'")
                        all_buttons.extend(text_buttons)
                        
                    # Try with contains
                    xpath = f"//*[contains(text(), '{text}')]"
                    text_buttons = self.driver.find_elements(By.XPATH, xpath)
                    if text_buttons:
                        logger.info(f"Found {len(text_buttons)} buttons containing text: '{text}'")
                        all_buttons.extend(text_buttons)
                except Exception:
                    pass
            
            # Remove duplicates and keep only visible buttons
            unique_buttons = []
            button_ids = set()
            
            for button in all_buttons:
                try:
                    # Use the selenium internal ID to identify unique elements
                    elem_id = button.id
                    if elem_id not in button_ids:
                        button_ids.add(elem_id)
                        
                        # Only include visible buttons
                        if button.is_displayed():
                            unique_buttons.append(button)
                except Exception:
                    pass
            
            logger.info(f"Found {len(unique_buttons)} unique coupon buttons")
            return unique_buttons
            
        except Exception as e:
            logger.warning(f"Error in coupon button detection: {e}")
            return []
    
    def _find_weis_buttons_directly(self):
        """
        Specialized function to find Weis coupon buttons directly by examining the page structure.
        
        Returns:
            list: List of found coupon buttons
        """
        try:
            buttons = []
            
            # Try several specific selectors known to work well for Weis
            selectors = [
                ".btn-clip:not(.added)",
                ".coupon-add",
                ".add-coupon",
                "button[data-coupon-id]",
                "button.coupon__btn",
                "button.add"
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"Found {len(elements)} Weis buttons with selector: {selector}")
                        buttons.extend(elements)
                except Exception:
                    pass
            
            # Try to find buttons with specific text "CLIP COUPON" (common in Weis)
            try:
                # Exact match for "CLIP COUPON" text
                xpath = "//*[text()='CLIP COUPON']"
                text_buttons = self.driver.find_elements(By.XPATH, xpath)
                if text_buttons:
                    logger.info(f"Found {len(text_buttons)} buttons with exact text 'CLIP COUPON'")
                    buttons.extend(text_buttons)
            except Exception:
                pass
                
            # If we've found a lot of buttons, filter them for uniqueness
            if len(buttons) > 0:
                # Remove duplicates
                unique_buttons = []
                button_ids = set()
                
                for button in buttons:
                    try:
                        elem_id = button.id
                        if elem_id not in button_ids:
                            button_ids.add(elem_id)
                            
                            # Only include visible buttons
                            if button.is_displayed():
                                unique_buttons.append(button)
                    except Exception:
                        pass
                
                logger.info(f"Found {len(unique_buttons)} unique Weis buttons")
                return unique_buttons
            
            return buttons
            
        except Exception as e:
            logger.error(f"Error in direct Weis button detection: {e}")
            return []
    
    def _is_already_clipped(self, button, website_config):
        """
        Check if a coupon has already been clipped.
        """
        try:
            # For Harris Teeter, check if the button text contains "Unclip"
            button_text = button.text.lower()
            if "unclip" in button_text:
                logger.debug(f"Button is for unclipping, not clipping: '{button_text}'")
                return True
            
            # Check the button's class for clipped indicators
            if "coupon_clipped_indicator" in website_config:
                indicator_classes = website_config["coupon_clipped_indicator"].split(", ")
                button_class = button.get_attribute("class") or ""
                
                for indicator_class in indicator_classes:
                    # Skip empty indicators
                    if not indicator_class.strip():
                        continue
                        
                    # Check if this class indicator is present
                    if indicator_class in button_class:
                        return True
            
            # Check button text for common "clipped" indicators
            clipped_terms = ["clipped", "added", "saved", "in cart", "remove"]
            if any(term in button_text for term in clipped_terms):
                return True
            
            # Check for disabled attribute
            if button.get_attribute("disabled") == "true" or button.get_attribute("disabled") == "":
                return True
            
            # Check for aria-disabled attribute
            if button.get_attribute("aria-disabled") == "true":
                return True
                
            return False
                
        except Exception as e:
            logger.debug(f"Error checking if coupon is clipped: {e}")
            return False  # Assume not clipped if we can't determine
    
    def _click_button(self, button):
        """
        Attempt to click a button with retry logic for common issues.
        """
        settings = self.config["settings"]
        max_retries = settings.get("max_retries", 3)
        
        for attempt in range(max_retries):
            try:
                # First try to scroll the button into view
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                time.sleep(0.5)  # Brief pause after scrolling
                
                # Try a regular click first
                button.click()
                return True
                
            except ElementClickInterceptedException:
                # If regular click fails, try JavaScript click
                try:
                    self.driver.execute_script("arguments[0].click();", button)
                    return True
                except Exception:
                    pass
                    
            except Exception:
                # Wait before retry
                time.sleep(1)
                
            # If we get here, both approaches failed, try another technique
            try:
                # Use ActionChains for more complex click interaction
                actions = ActionChains(self.driver)
                actions.move_to_element(button).click().perform()
                return True
            except Exception:
                # If that fails too, wait and try next attempt
                time.sleep(1)
                
        logger.warning(f"Failed to click button after {max_retries} attempts")
        return False
        
    def _enhanced_click_button(self, button):
        """
        Enhanced version of button clicking specifically for Weis website.
        Uses multiple specialized techniques to ensure clicks work.
        
        Args:
            button: The WebElement button to click
            
        Returns:
            bool: True if successful, False otherwise
        """
        # First, make sure the button is visible before trying to click
        try:
            # Scroll the button into view, making sure it's centered
            self.driver.execute_script("""
                arguments[0].scrollIntoView({
                    behavior: 'smooth',
                    block: 'center',
                    inline: 'center'
                });
            """, button)
            time.sleep(0.5)  # Wait for smooth scroll
            
            # Verify button is visible and clickable
            if not button.is_displayed() or not button.is_enabled():
                logger.debug("Button is not visible or enabled")
                return False
            
            # Get button dimensions to make sure it's not too small
            size = button.size
            if size['width'] < 5 or size['height'] < 5:
                logger.debug(f"Button is too small: {size}")
                return False
            
            # Try multiple click techniques in sequence
            
            # 1. Standard click
            try:
                button.click()
                time.sleep(0.5)
                return True
            except Exception as e:
                logger.debug(f"Standard click failed: {e}")
            
            # 2. JavaScript click
            try:
                self.driver.execute_script("arguments[0].click();", button)
                time.sleep(0.5)
                return True
            except Exception as e:
                logger.debug(f"JavaScript click failed: {e}")
            
            # 3. Action chains with move and click
            try:
                actions = ActionChains(self.driver)
                actions.move_to_element(button).click().perform()
                time.sleep(0.5)
                return True
            except Exception as e:
                logger.debug(f"ActionChains click failed: {e}")
            
            # 4. Try clicking the center of the button with coordinates
            try:
                rect = self.driver.execute_script("""
                    var rect = arguments[0].getBoundingClientRect();
                    return {
                        left: rect.left,
                        top: rect.top,
                        width: rect.width,
                        height: rect.height
                    };
                """, button)
                
                center_x = rect['left'] + rect['width'] / 2
                center_y = rect['top'] + rect['height'] / 2
                
                # Use ActionChains to move to coordinates and click
                actions = ActionChains(self.driver)
                actions.move_by_offset(center_x, center_y).click().perform()
                time.sleep(0.5)
                return True
            except Exception as e:
                logger.debug(f"Coordinate click failed: {e}")
            
            # 5. Try to get parent element and click it instead
            try:
                parent = button.find_element(By.XPATH, "..")
                self.driver.execute_script("arguments[0].click();", parent)
                time.sleep(0.5)
                return True
            except Exception as e:
                logger.debug(f"Parent click failed: {e}")
            
            # 6. Send Enter key as last resort
            try:
                button.send_keys(Keys.ENTER)
                time.sleep(0.5)
                return True
            except Exception as e:
                logger.debug(f"Enter key failed: {e}")
            
            logger.warning("All click techniques failed")
            return False
            
        except Exception as e:
            logger.warning(f"Error in enhanced button click: {e}")
            return False
        
    def _is_rate_limited(self, website_config, settings):
        """
        Improved rate limit detection with better contextual awareness and thresholds.
        
        Args:
            website_config (dict): Website configuration
            settings (dict): Settings dictionary
            
        Returns:
            bool: True if rate limiting is detected, False otherwise
        """
        # If rate limit detection is disabled, always return False
        if not settings.get("enable_rate_limit_detection", True):
            return False
        
        detected = False
        context = None
        
        try:
            # First, check if we're only looking at main content
            if settings.get("rate_limit_check_main_content_only", True):
                # Focus on the main content areas to avoid false positives in footers, etc.
                main_selectors = ["main", "#main", ".main-content", "#content", ".content", "article"]
                main_content = None
                
                for selector in main_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(e.is_displayed() for e in elements):
                        main_content = next(e for e in elements if e.is_displayed())
                        break
                
                if main_content:
                    context = main_content
                else:
                    # Fallback to the entire body if no main content area found
                    context = self.driver.find_element(By.TAG_NAME, "body")
            else:
                # Check the entire page source
                context = self.driver.page_source
            
            # Look for rate limit indicators in the appropriate context
            for indicator in website_config.get("rate_limit_indicators", []):
                if context == self.driver.page_source:
                    # If checking the page source
                    if indicator in context:
                        logger.warning(f"Rate limit indicator found in page source: '{indicator}'")
                        detected = True
                        break
                else:
                    # If checking an element
                    context_text = context.text.lower()
                    if indicator.lower() in context_text:
                        logger.warning(f"Rate limit indicator found in main content: '{indicator}'")
                        detected = True
                        break
            
            # If no specific indicators found, check for generic phrases that might indicate rate limiting
            if not detected and context != self.driver.page_source:
                # These are more specific phrases than "please try again later" to avoid false positives
                rate_limit_phrases = [
                    "rate limit",
                    "too many requests",
                    "too many attempts",
                    "try again later",
                    "temporarily blocked"
                ]
                
                context_text = context.text.lower()
                matched_phrase = None
                
                for phrase in rate_limit_phrases:
                    if phrase in context_text:
                        matched_phrase = phrase
                        break
                        
                if matched_phrase:
                    # If we found a common phrase, increase our count
                    self.rate_limit_count += 1
                    logger.warning(f"Potential rate limit phrase detected: '{matched_phrase}' (count: {self.rate_limit_count})")
                    
                    # Only consider it a true rate limit if we've seen multiple indications
                    threshold = settings.get("rate_limit_threshold", 3)
                    if self.rate_limit_count >= threshold:
                        logger.warning(f"Rate limit threshold reached ({threshold})")
                        detected = True
                    else:
                        # Not enough occurrences yet to consider it a rate limit
                        logger.info(f"Below rate limit threshold ({self.rate_limit_count}/{threshold})")
                else:
                    # Reset the count if we don't see a phrase this time
                    self.rate_limit_count = 0
            
            return detected
                
        except Exception as e:
            logger.error(f"Error checking for rate limiting: {e}")
            return False
        
    def _handle_rate_limit(self, settings):
        """
        Handle rate limiting with more gradual backoff.
        
        Returns:
            bool: True if the page was refreshed and buttons should be re-found
        """
        # Calculate backoff time (with less aggressive growth)
        backoff_factor = settings.get("rate_limit_backoff_factor", 1.5)
        max_backoff = settings.get("max_backoff_time", 30)
        
        wait_time = min(max_backoff, self.backoff_time)
        
        logger.info(f"Rate limited. Backing off for {wait_time} seconds")
        print(f"\nRate limit detected. Waiting {wait_time} seconds before continuing...")
        time.sleep(wait_time)
        
        # Increase backoff for next time, but less aggressively
        self.backoff_time = min(max_backoff, self.backoff_time * backoff_factor)
        
        # Try refreshing the page
        logger.info("Refreshing page after rate limit")
        self.driver.refresh()
        time.sleep(3)  # Wait for refresh to complete
        
        # Return True to indicate page was refreshed and buttons should be re-found
        return True
    
    def _ask_user_to_identify_button(self):
        """
        Ask the user to help identify a coupon button when automatic detection fails.
        
        Returns:
            list: List of buttons based on user's selection
        """
        print("\n" + "="*50)
        print("Automatic button detection failed. Would you like to:")
        print("1. Tell me what to click (recommended)")
        print("2. Skip this website")
        print("="*50)
        
        try:
            choice = input("Enter your choice (1-2, default: 1): ") or "1"
            
            if choice == "2":
                return []
            
            print("\nPlease look at the webpage and tell me what to click.")
            print("Options:")
            print("1. Describe a CSS selector (e.g., 'button.clip-coupon')")
            print("2. Describe text on the button (e.g., 'Clip Coupon')")
            
            identify_choice = input("Enter your choice (1-2, default: 2): ") or "2"
            
            if identify_choice == "1":
                selector = input("Enter the CSS selector: ")
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        logger.info(f"Found {len(buttons)} buttons with user-provided selector: {selector}")
                        return buttons
                    else:
                        print("No buttons found with that selector.")
                        return []
                except Exception as e:
                    logger.error(f"Error with user-provided selector: {e}")
                    return []
            else:
                button_text = input("Enter the text on the button: ")
                try:
                    # Try exact text match first
                    xpath = f"//*[text()='{button_text}']"
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    
                    if not buttons:
                        # Try case-insensitive XPath text match
                        xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{button_text.lower()}')]"
                        buttons = self.driver.find_elements(By.XPATH, xpath)
                        
                    if buttons:
                        logger.info(f"Found {len(buttons)} buttons with text containing: {button_text}")
                        return buttons
                    else:
                        print("No buttons found with that text.")
                        return []
                except Exception as e:
                    logger.error(f"Error with text search: {e}")
                    return []
                
        except KeyboardInterrupt:
            return []
            
    def _control_menu(self, clipped, remaining):
        """
        Show control menu when user presses Ctrl+C.
        
        Args:
            clipped (int): Number of coupons clipped so far
            remaining (int): Number of coupons remaining
            
        Returns:
            str: User's choice ('c' for continue, 'q' for quit, 's' for return to selection, 'r' for reconnect)
        """
        print("\n" + "="*50)
        print(f"PAUSED: {clipped} coupons clipped, ~{remaining} remaining")
        print("="*50)
        print("Options:")
        print("1. Continue clipping")
        print("2. Skip to next website")
        print("3. Return to website selection menu")
        print("4. Quit program")
        print("5. Toggle rate limit detection")
        print("6. Reconnect to browser (fix connection issues)")
        
        try:
            choice = input("Select option (1-6, default: 1): ") or "1"
        except KeyboardInterrupt:
            # Handle Ctrl+C during input too
            return 'q'
            
        if choice == "2":
            return 'q'  # Skip to next website
        elif choice == "3":
            return 's'  # Return to website selection
        elif choice == "4":
            self.close()
            exit(0)  # Exit program
        elif choice == "5":
            # Toggle rate limit detection
            settings = self.config["settings"]
            current_state = settings.get("enable_rate_limit_detection", True)
            settings["enable_rate_limit_detection"] = not current_state
            print(f"Rate limit detection {'disabled' if current_state else 'enabled'}")
            return 'c'  # Continue
        elif choice == "6":
            return 'r'  # Reconnect to browser
        else:
            return 'c'  # Continue
        
    def close(self):
        """Close the WebDriver when finished."""
        if not self.driver:
            return
            
        try:
            self.driver.quit()
            logger.info("WebDriver closed successfully")
        except Exception as e:
            logger.error(f"Error closing WebDriver: {e}")

def main():
    """Main entry point for the coupon clipper program."""
    try:
        print("="*60)
        print("Grocery Coupon Clipper".center(60))
        print("="*60)
        
        # Ask if the user wants to attach to an existing Chrome instance
        print("\nOptions:")
        print("1. Launch Chrome with your default profile (saved logins)")
        print("2. Launch Chrome with a clean profile")
        print("3. Connect to already running Chrome instance")
        
        choice = input("\nSelect option (1-3, default: 1): ") or "1"
        
        attach = True
        use_default_profile = True
        
        if choice == "2":
            use_default_profile = False
        elif choice == "3":
            print("\nMake sure Chrome is already running with remote debugging enabled.")
            print("If not, close Chrome and select option 1 or 2 instead.")
            input("Press Enter to continue...")
            
        # Create the coupon clipper with options
        clipper = CouponClipper(attach_to_existing=attach)
        clipper._use_default_profile = use_default_profile
        
        # Set up driver once
        clipper.setup_driver(attach)
        
        # Website selection loop
        while True:
            # Show available websites
            print("\nAvailable websites:")
            for i, website in enumerate(clipper.config["websites"].keys(), 1):
                print(f"{i}. {website}")
                
            # Ask which website to use
            try:
                website_idx = int(input("\nSelect website number (or 0 to exit): ")) - 1
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue
                
            if website_idx == -1:
                break
                
            websites = list(clipper.config["websites"].keys())
            
            if 0 <= website_idx < len(websites):
                selected_website = websites[website_idx]
                print(f"\nClipping coupons for {selected_website}...")
                
                # Clip coupons for the selected website
                try:
                    continue_loop = clipper.clip_coupons(selected_website)
                    # The clip_coupons method will return to the menu when done or interrupted
                except KeyboardInterrupt:
                    print("\nOperation interrupted by user.")
                except Exception as e:
                    # Ask if the user wants to continue with website selection
                    if input("\nReturn to website selection? (y/n, default: y): ").lower() != 'n':
                        continue
                    else:
                        break
            else:
                print("Invalid selection.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if 'clipper' in locals():
            clipper.close()
        print("\nCoupon clipper finished.")

if __name__ == "__main__":
    main()
