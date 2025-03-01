import os
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('selenium-tests')

def save_screenshot(driver, name):
    """Save a screenshot to the screenshots directory"""
    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    filename = f"{int(time.time())}_{name}.png"
    filepath = screenshots_dir / filename
    
    try:
        driver.save_screenshot(str(filepath))
        logger.info(f"Screenshot saved to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")

def save_page_source(driver, name):
    """Save the page source to a file"""
    output_dir = Path(__file__).parent / "page_source"
    output_dir.mkdir(exist_ok=True)
    
    filename = f"{int(time.time())}_{name}.html"
    filepath = output_dir / filename
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info(f"Page source saved to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save page source: {e}")

def debug_page_state(driver, test_name):
    """Capture the current page state for debugging"""
    logger.info(f"Debug info for test: {test_name}")
    logger.info(f"Current URL: {driver.current_url}")
    logger.info(f"Page title: {driver.title}")
    
    # Check if key elements exist
    try:
        tabulator_present = driver.execute_script('return !!document.querySelector(".tabulator")')
        logger.info(f"Tabulator present: {tabulator_present}")
        
        tableholder_present = driver.execute_script('return !!document.querySelector(".tabulator-tableHolder")')
        logger.info(f"TableHolder present: {tableholder_present}")
        
        cells_count = driver.execute_script('return document.querySelectorAll(".tabulator-cell").length')
        logger.info(f"Number of cells found: {cells_count}")
        
        buttons_count = driver.execute_script('return document.querySelectorAll("button").length')
        logger.info(f"Number of buttons found: {buttons_count}")
    except Exception as e:
        logger.error(f"Error checking elements: {e}")
    
    save_screenshot(driver, test_name)
    save_page_source(driver, test_name)
