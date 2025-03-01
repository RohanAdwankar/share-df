import os
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_utils')

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
    """Capture debugging information about the current page state"""
    try:
        # Create logs directory if it doesn't exist
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Generate a filename with timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{test_name}-{timestamp}"
        
        # Log basic page information
        logger.info(f"Debug for {test_name}: Title = {driver.title}, URL = {driver.current_url}")
        
        # Try to save page source
        try:
            with open(log_dir / f"{filename}.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info(f"Saved page source to {filename}.html")
        except Exception as e:
            logger.error(f"Failed to save page source: {e}")
        
        # Try to take a screenshot
        try:
            driver.save_screenshot(str(log_dir / f"{filename}.png"))
            logger.info(f"Saved screenshot to {filename}.png")
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
        
        # Log JavaScript errors if any
        try:
            logs = driver.get_log('browser')
            if logs:
                logger.info("Browser logs:")
                for log in logs:
                    logger.info(f"  {log}")
        except Exception as e:
            logger.error(f"Failed to get browser logs: {e}")
            
        # Count elements on page
        try:
            elements = {
                "tables": len(driver.find_elements(by="css selector", value=".tabulator")),
                "cells": len(driver.find_elements(by="css selector", value=".tabulator-cell")),
                "rows": len(driver.find_elements(by="css selector", value=".tabulator-row")),
                "columns": len(driver.find_elements(by="css selector", value=".tabulator-col")),
                "errors": len(driver.find_elements(by="css selector", value=".error-message"))
            }
            logger.info(f"Page elements: {elements}")
        except Exception as e:
            logger.error(f"Failed to count elements: {e}")
            
    except Exception as e:
        logger.error(f"Error in debug_page_state: {e}")
