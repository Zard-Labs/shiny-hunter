"""Command builder for ESP32-C6 button commands."""
from enum import IntEnum


class ButtonCommand(IntEnum):
    """Button command codes for ESP32-C6."""
    RELEASE = 0x00
    BTN_A = 0x01
    BTN_B = 0x02
    BTN_X = 0x03
    BTN_Y = 0x04
    BTN_L = 0x05
    BTN_R = 0x06
    BTN_ZL = 0x07
    BTN_ZR = 0x08
    BTN_PLUS = 0x09  # START
    BTN_MINUS = 0x0A  # SELECT
    BTN_HOME = 0x0B
    BTN_CAPTURE = 0x0C
    
    DPAD_UP = 0x10
    DPAD_DOWN = 0x11
    DPAD_LEFT = 0x12
    DPAD_RIGHT = 0x13
    
    RESET = 0x20  # A+B+PLUS+MINUS combo
    
    STATUS_REQUEST = 0xF0
    RECONNECT = 0xF1


BUTTON_MAP = {
    'RELEASE': ButtonCommand.RELEASE,
    'A': ButtonCommand.BTN_A,
    'B': ButtonCommand.BTN_B,
    'X': ButtonCommand.BTN_X,
    'Y': ButtonCommand.BTN_Y,
    'L': ButtonCommand.BTN_L,
    'R': ButtonCommand.BTN_R,
    'ZL': ButtonCommand.BTN_ZL,
    'ZR': ButtonCommand.BTN_ZR,
    'START': ButtonCommand.BTN_PLUS,
    'PLUS': ButtonCommand.BTN_PLUS,
    'SELECT': ButtonCommand.BTN_MINUS,
    'MINUS': ButtonCommand.BTN_MINUS,
    'HOME': ButtonCommand.BTN_HOME,
    'CAPTURE': ButtonCommand.BTN_CAPTURE,
    'UP': ButtonCommand.DPAD_UP,
    'DOWN': ButtonCommand.DPAD_DOWN,
    'LEFT': ButtonCommand.DPAD_LEFT,
    'RIGHT': ButtonCommand.DPAD_RIGHT,
    'RESET': ButtonCommand.RESET,
}


def build_command(button: str) -> int:
    """
    Build command byte for given button.
    
    Args:
        button: Button name (e.g., 'A', 'START', 'UP')
    
    Returns:
        Command byte as integer
    
    Raises:
        ValueError: If button name is invalid
    """
    button_upper = button.upper()
    if button_upper not in BUTTON_MAP:
        raise ValueError(f"Invalid button: {button}. Valid buttons: {list(BUTTON_MAP.keys())}")
    
    return BUTTON_MAP[button_upper]


def get_button_name(cmd: int) -> str:
    """
    Get button name from command byte.
    
    Args:
        cmd: Command byte
    
    Returns:
        Button name or 'UNKNOWN'
    """
    for name, value in BUTTON_MAP.items():
        if value == cmd:
            return name
    return 'UNKNOWN'
