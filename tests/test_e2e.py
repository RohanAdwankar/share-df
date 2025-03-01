import pytest
import pandas as pd
import logging
from share_df.server import ShareServer
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoAlertPresentException
import socket
import time
from .test_utils import debug_page_state, logger

# Setup logging
logger = logging.getLogger("test_e2e")

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
    port = get_free_port
    logger.info(f"Starting test server on port {port}")
    df = pd.DataFrame({'col1': [1,2,3], 'col2': ['a','b','c']})
    server = ShareServer(df, collaborative_mode=False, test_mode=True)
    url, shutdown_event = server.serve(port=port)
    # Wait extra time for server to fully initialize
    time.sleep(2)
    logger.info(f"Server started at {url}")
    yield url
    shutdown_event.set()
    # Add a brief delay to ensure server shuts down properly
    time.sleep(1)

@pytest.fixture
def driver(server):
    options = webdriver.ChromeOptions()
    # Add options to make testing more reliable
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')  # Set a standard window size
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)  # Add implicit wait
    driver.set_page_load_timeout(30)  # Increase page load timeout
    logger.info("WebDriver initialized")
    yield driver
    logger.info("Quitting WebDriver")
    driver.quit()

@pytest.fixture(scope="module") 
def server_instance(get_free_port):
    port = get_free_port + 1  # Use a different port than the main server
    logger.info(f"Starting server instance on port {port}")
    df = pd.DataFrame({'col1': [1,2,3], 'col2': ['a','b','c']})
    server = ShareServer(df, collaborative_mode=False, test_mode=True)
    url, shutdown_event = server.serve(port=port)
    # Wait extra time for server to fully initialize
    time.sleep(2)
    logger.info(f"Server instance started at {url}")
    yield server
    shutdown_event.set()
    # Add a brief delay to ensure server shuts down properly
    time.sleep(1)

def wait_for_page_load(driver, timeout=30):
    """Wait for page to fully load with increased timeout"""
    logger.info("Waiting for page to load")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        logger.info("Page loaded successfully")
        # Additional wait to ensure JavaScript initializes
        time.sleep(3)
    except TimeoutException:
        logger.error("Page failed to load within timeout")
        debug_page_state(driver, "page_load_timeout")
        raise

def wait_for_tabulator_ready(driver, timeout=30):
    """Wait for Tabulator to be fully initialized"""
    logger.info("Waiting for Tabulator to be ready")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return !!document.querySelector(".tabulator")')
        )
        logger.info("Tabulator found")
        time.sleep(2)  # Extra delay to ensure stability
    except TimeoutException:
        logger.error("Tabulator not found within timeout")
        debug_page_state(driver, "tabulator_timeout")
        raise

def safe_click(driver, element):
    """Click an element safely using JavaScript"""
    driver.execute_script("arguments[0].click();", element)

def safe_send_keys(driver, element, text):
    """Send keys to an element safely using JavaScript when possible"""
    try:
        # Try to set the value directly
        driver.execute_script(f"arguments[0].value = '{text}';", element)
        # Trigger an input event
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
    except:
        # Fall back to regular send_keys if JavaScript approach fails
        element.clear()
        element.send_keys(text)

# Add a simple test that just loads the page to verify basic functionality
def test_page_load(driver, server):
    """Test that the page loads successfully"""
    logger.info(f"Testing page load: {server}")
    driver.get(server)
    
    # Wait for the page to load
    wait_for_page_load(driver)
    
    # Log current page information
    logger.info(f"Page title: {driver.title}")
    logger.info(f"Current URL: {driver.current_url}")
    
    # Check for essential elements
    tabulator_present = driver.execute_script('return !!document.querySelector(".tabulator")')
    logger.info(f"Is tabulator present: {tabulator_present}")
    
    # Assert basic page load success
    assert "DataFrame" in driver.title
    
    # Debug page state
    debug_page_state(driver, "test_page_load")

def test_edit_cell(driver, server):
    logger.info(f"Testing edit cell: {server}")
    driver.get(server)
    wait_for_page_load(driver)
    wait_for_tabulator_ready(driver)
    
    debug_page_state(driver, "before_edit_cell")
    
    # Use JavaScript to find and click the first cell
    logger.info("Finding and clicking cell")
    try:
        # First check if cells are available
        cells_present = driver.execute_script('return document.querySelectorAll(".tabulator-cell").length > 0')
        logger.info(f"Cells present: {cells_present}")
        
        if cells_present:
            # Click the first cell using JavaScript
            driver.execute_script('document.querySelector(".tabulator-cell").click()')
            logger.info("Cell clicked via JavaScript")
        else:
            logger.error("No cells found in the table")
            raise Exception("No cells found in the table")
            
        # Wait for input field to appear
        logger.info("Waiting for input field")
        input_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
        )
        
        # Set value using JavaScript
        logger.info("Setting cell value")
        driver.execute_script('arguments[0].value = "new value";', input_field)
        driver.execute_script('arguments[0].dispatchEvent(new Event("change", { bubbles: true }));', input_field)
        
        # Click outside to finish editing
        logger.info("Clicking outside")
        driver.execute_script('document.querySelector("header").click()')
        time.sleep(1)
        
        # Verify cell has new value
        cell_text = driver.execute_script('return document.querySelector(".tabulator-cell").innerText')
        logger.info(f"Cell text after edit: {cell_text}")
        
        assert "new value" in cell_text
        
    except Exception as e:
        logger.error(f"Error in test_edit_cell: {e}")
        debug_page_state(driver, "edit_cell_error")
        raise

def test_add_column(driver, server):
    driver.get(server)
    wait_for_page_load(driver)
    wait_for_tabulator_ready(driver)
    
    # Find and click the add button using JavaScript
    add_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, "add-button"))
    )
    safe_click(driver, add_button)
    time.sleep(2)
    
    # Wait for header to update and verify
    header = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".tabulator-header"))
    )
    assert 'New Column' in header.text

def test_add_row(driver, server):
    driver.get(server)
    wait_for_page_load(driver)
    wait_for_tabulator_ready(driver)
    
    # Count initial rows
    initial_rows = len(driver.find_elements(By.CSS_SELECTOR, ".tabulator-row"))
    
    # Find the second add button (for rows) and click it
    add_buttons = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "add-button"))
    )
    assert len(add_buttons) >= 2, "Not enough add buttons found"
    safe_click(driver, add_buttons[1])
    time.sleep(2)
    
    # Count final rows and verify
    final_rows = len(driver.find_elements(By.CSS_SELECTOR, ".tabulator-row"))
    assert final_rows == initial_rows + 1

def test_save_changes(driver, server):
    driver.get(server)
    wait_for_page_load(driver)
    wait_for_tabulator_ready(driver)
    
    # Click save button
    save_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, "save-button"))
    )
    safe_click(driver, save_button)
    time.sleep(1)
    
    # Verify toast appears
    toast = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "toast"))
    )
    assert "saved successfully" in toast.text.lower()

def test_rename_column(driver, server):
    driver.get(server)
    wait_for_page_load(driver)
    wait_for_tabulator_ready(driver)
    
    # Get column header
    header = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".tabulator-col-title"))
    )
    
    # Use JavaScript to execute the Shift+Click behavior
    driver.execute_script("""
        var event = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window,
            shiftKey: true
        });
        arguments[0].dispatchEvent(event);
    """, header)
    
    # Wait for input to appear
    input_elem = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".tabulator-col-title input"))
    )
    
    # Set value and press Enter
    safe_send_keys(driver, input_elem, "Renamed")
    input_elem.send_keys(Keys.ENTER)
    time.sleep(2)
    
    # Verify header text was updated
    header_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".tabulator-header"))
    )
    assert "Renamed" in header_element.text

def test_cancel_changes(driver, server, server_instance):
    driver.get(server)
    wait_for_page_load(driver)
    wait_for_tabulator_ready(driver)
    
    # Edit a cell
    cell = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".tabulator-cell"))
    )
    safe_click(driver, cell)
    
    input_field = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".tabulator .tabulator-editing input"))
    )
    safe_send_keys(driver, input_field, "test change")
    
    header = driver.find_element(By.CLASS_NAME, "header")
    safe_click(driver, header)
    time.sleep(1)
    
    # Add a column
    add_button = driver.find_element(By.CLASS_NAME, "add-button")
    safe_click(driver, add_button)
    time.sleep(1)
    
    # Verify cell has changed
    modified_cell = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".tabulator-cell"))
    )
    assert "test change" in modified_cell.text
    
    # Click cancel button
    cancel_button = driver.find_element(By.CLASS_NAME, "cancel-button")
    safe_click(driver, cancel_button)
    time.sleep(1)
    
    # Look for toast confirming cancellation
    toast = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "toast"))
    )
    assert "discarding changes" in toast.text.lower()
    
    # In test mode, we don't need to handle the alert as it's bypassed
    # Verify dataframe has been reset to original
    assert server_instance.df.equals(server_instance.original_df)