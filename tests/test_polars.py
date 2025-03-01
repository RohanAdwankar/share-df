import pytest
import pandas as pd
import polars as pl
import logging
from share_df.server import ShareServer
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import socket
import time
from .test_utils import debug_page_state, logger

# Setup logging
logger = logging.getLogger("test_polars")

@pytest.fixture(scope="function", autouse=True)
def enable_test_mode():
    # Set test mode environment variable directly
    os.environ['SHARE_DF_TEST_MODE'] = 'true'
    yield
    # Unset after test
    os.environ.pop('SHARE_DF_TEST_MODE', None)

@pytest.fixture(scope="module")
def get_free_port():
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

@pytest.fixture(scope="module") 
def server(get_free_port):
    port = get_free_port + 100  # Use a different port range than other tests
    logger.info(f"Starting polars test server on port {port}")
    # Use polars DataFrame
    df = pl.DataFrame({'col1': [1,2,3], 'col2': ['a','b','c']})
    server = ShareServer(df, collaborative_mode=False, test_mode=True)
    url, shutdown_event = server.serve(port=port)
    # Wait extra time for server to fully initialize
    time.sleep(2)
    logger.info(f"Polars server started at {url}")
    yield url
    logger.info("Shutting down polars server")
    shutdown_event.set()
    # Add a brief delay to ensure server shuts down properly
    time.sleep(1)

@pytest.fixture
def driver(server):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')  # Set a standard window size
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)  # Add implicit wait
    driver.set_page_load_timeout(30)  # Increase page load timeout
    logger.info("WebDriver initialized for polars tests")
    yield driver
    logger.info("Quitting WebDriver for polars tests")
    driver.quit()

# Add a simple test that just loads the page to verify basic functionality
def test_page_load_polars(driver, server):
    """Test that the page loads successfully with polars data"""
    logger.info(f"Testing polars page load: {server}")
    driver.get(server)
    
    # Wait for the page to load
    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        logger.info("Page loaded successfully")
        # Additional wait to ensure JavaScript initializes
        time.sleep(3)
    except TimeoutException:
        logger.error("Page failed to load within timeout")
        debug_page_state(driver, "polars_page_load_timeout")
        raise
    
    # Log current page information
    logger.info(f"Page title: {driver.title}")
    logger.info(f"Current URL: {driver.current_url}")
    
    # Check for essential elements
    tabulator_present = driver.execute_script('return !!document.querySelector(".tabulator")')
    logger.info(f"Is tabulator present: {tabulator_present}")
    
    # Assert basic page load success
    assert "DataFrame" in driver.title
    
    # Debug page state
    debug_page_state(driver, "test_page_load_polars")

def test_polars_edit_cell(driver, server):
    logger.info(f"Testing polars edit cell: {server}")
    driver.get(server)
    
    # Wait for the page to load
    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        logger.info("Page loaded successfully")
        time.sleep(3)
    except TimeoutException:
        logger.error("Page failed to load within timeout")
        debug_page_state(driver, "polars_edit_cell_page_load")
        raise
    
    # Wait for tabulator to be ready
    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script('return !!document.querySelector(".tabulator")')
        )
        logger.info("Tabulator found")
        time.sleep(2)
    except TimeoutException:
        logger.error("Tabulator not found within timeout")
        debug_page_state(driver, "polars_edit_cell_tabulator")
        raise
    
    debug_page_state(driver, "before_polars_edit_cell")
    
    try:
        # First check if cells are available using JavaScript
        cells_present = driver.execute_script('return document.querySelectorAll(".tabulator-cell").length > 0')
        logger.info(f"Cells present: {cells_present}")
        
        if cells_present:
            # Click the first cell using JavaScript
            driver.execute_script('document.querySelector(".tabulator-cell").click()')
            logger.info("Cell clicked via JavaScript")
        else:
            logger.error("No cells found in the polars table")
            raise Exception("No cells found in the polars table")
        
        # Wait for input field to appear
        logger.info("Waiting for input field")
        input_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
        )
        
        # Set value using JavaScript
        logger.info("Setting cell value")
        driver.execute_script('arguments[0].value = "polars value";', input_field)
        driver.execute_script('arguments[0].dispatchEvent(new Event("change", { bubbles: true }));', input_field)
        
        # Click outside to finish editing
        logger.info("Clicking outside")
        driver.execute_script('document.querySelector("header").click()')
        time.sleep(1)
        
        # Verify cell has new value
        cell_text = driver.execute_script('return document.querySelector(".tabulator-cell").innerText')
        logger.info(f"Cell text after edit: {cell_text}")
        
        assert "polars value" in cell_text
    
    except Exception as e:
        logger.error(f"Error in test_polars_edit_cell: {e}")
        debug_page_state(driver, "polars_edit_cell_error")
        raise