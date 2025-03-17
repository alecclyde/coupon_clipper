# Grocery Coupon Clipper

**⚠️ DISCLAIMER: This tool is provided for EDUCATIONAL PURPOSES ONLY to demonstrate browser automation techniques. ⚠️**

Grocery Coupon Clipper is an educational Python tool that demonstrates browser automation for digital coupon websites. It showcases techniques for interacting with dynamic web content, detecting and handling CAPTCHAs, emulating human-like behavior, and working with session management.

This project is meant to illustrate programming concepts including:
- Selenium WebDriver implementation
- Human interaction emulation
- Error handling and recovery
- Session persistence
- Dynamic web element detection

## Features

- **Browser Integration**: Works with your existing Chrome profile to maintain login sessions
- **Human Emulation**: Mimics realistic human behavior with variable mouse movements and timing
- **Multi-Site Support**: Compatible with several major grocery store websites
- **Adaptive Timing**: Adjusts clipping speed based on site response
- **CAPTCHA Detection**: Identifies and pauses for human intervention when security checks appear
- **Error Recovery**: Automatically handles common error scenarios and connection issues
- **Session Management**: Maintains progress between runs
- **Anti-Detection Measures**: Implements browser stealth techniques for educational demonstration

## Supported Websites

The tool currently supports these grocery sites for educational demonstration:
- Food Lion
- Safeway
- Weis Markets
- Giant Food
- Harris Teeter
- Walmart

## Installation

### Prerequisites

- Python 3.7+
- Chrome browser
- pip (Python package manager)

### Setup

1. Clone this repository:
```bash
git clone https://github.com/yourusername/grocery-coupon-clipper.git
cd grocery-coupon-clipper
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

The main dependencies include:
- selenium
- psutil

## Usage

Run the main script:
```bash
python coupon_clipper.py
```

Follow the interactive prompts to:
1. Choose whether to use your existing Chrome profile (recommended)
2. Select which grocery website to demonstrate automation with
3. Set your preferred clipping speed

### Controls

During operation, you can press `Ctrl+C` at any time to access the control menu:
- Continue clipping
- Skip to next website
- Return to website selection menu
- Toggle rate limit detection
- Reconnect to browser
- Quit program

## Configuration

The tool uses a configuration file (`coupon_config.json`) that can be customized to adjust:
- Website-specific selectors
- Timing parameters
- Human emulation settings
- Rate limit detection strategies

## How It Works

For educational purposes, this tool demonstrates:

1. **Browser Interaction**: Shows how to control Chrome via Selenium WebDriver
2. **Element Detection**: Demonstrates finding dynamic elements on a page
3. **Human-Like Behavior**: Illustrates techniques to mimic human interactions:
   - Variable timing between actions
   - Realistic mouse movements
   - Random scrolling patterns
   - Natural click patterns with small jitter
4. **Error Handling**: Shows robust error recovery techniques
5. **Session Management**: Demonstrates maintaining state between program runs

## Educational Value

This project provides insights into:
- Modern web automation techniques
- Handling dynamic web content
- Browser fingerprinting countermeasures
- CAPTCHA detection strategies
- Simulating human behavior patterns
- Session persistence mechanisms

## License

This project is available under the MIT License - see the LICENSE file for details.

## Contributing

This is an educational project. Contributions that enhance the educational value or improve code quality are welcome.

---

**⚠️ IMPORTANT FINAL NOTICE ⚠️**

This tool is provided STRICTLY FOR EDUCATIONAL PURPOSES to demonstrate browser automation techniques. Using automation tools on websites may violate their Terms of Service. Always respect website terms and conditions. The author takes no responsibility for how this educational tool is used. By using this tool, you acknowledge you are solely responsible for compliance with all applicable website terms and conditions.
