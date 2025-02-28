
import os

# Global flag to determine if we're in test mode
_TEST_MODE = False

def is_test_mode():
    """Check if we're running in test mode"""
    return _TEST_MODE or os.environ.get('SHARE_DF_TEST_MODE') == '1'

def set_test_mode(enabled=True):
    """Set the test mode flag"""
    global _TEST_MODE
    _TEST_MODE = enabled
    if enabled:
        os.environ['SHARE_DF_TEST_MODE'] = '1'
    else:
        os.environ.pop('SHARE_DF_TEST_MODE', None)
