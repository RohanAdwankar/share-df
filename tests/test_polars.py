import pytest
import pandas as pd
import polars as pl
from share_df.server import ShareServer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.alert import Alert as SeleniumAlert
import socket
import time

@pytest.fixture(scope="module")
def get_free_port():
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

@pytest.fixture(scope="module")
def polars_server(get_free_port):
    df = pl.DataFrame({'col1': [1,2,3], 'col2': ['a','b','c']})
    server = ShareServer(df)
    url, shutdown_event = server.serve(port=get_free_port)
    yield url
    shutdown_event.set()

@pytest.fixture(scope="module")
def polars_server_instance(get_free_port):
    df = pl.DataFrame({'col1': [1,2,3], 'col2': ['a','b','c']})
    server = ShareServer(df)
    url, shutdown_event = server.serve(port=get_free_port)
    yield server
    shutdown_event.set()

@pytest.fixture
def driver(polars_server):
    driver = webdriver.Chrome()
    yield driver
    driver.quit()

def test_polars_edit_cell(driver, polars_server):
    driver.get(polars_server)
    time.sleep(2)
    driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").click()
    driver.find_element(By.CSS_SELECTOR, "input").send_keys("new value")
    driver.find_element(By.CLASS_NAME, "header").click()
    time.sleep(2)
    assert driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").text == "1new value"

def test_polars_add_column(driver, polars_server):
    driver.get(polars_server)
    time.sleep(2)
    
    driver.find_element(By.CLASS_NAME, "add-button").click()
    time.sleep(2)
    
    assert 'New Column' in driver.find_element(By.CSS_SELECTOR, ".tabulator-header").text

def test_polars_save_changes(driver, polars_server):
    driver.get(polars_server)
    time.sleep(2)
    
    # Make a change
    driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").click()
    driver.find_element(By.CSS_SELECTOR, "input").send_keys("test")
    driver.find_element(By.CLASS_NAME, "header").click()
    time.sleep(1)
    
    # Save changes
    driver.find_element(By.CLASS_NAME, "save-button").click()
    time.sleep(1)
    
    toast = driver.find_element(By.CLASS_NAME, "toast")
    assert "saved successfully" in toast.text.lower()

def test_polars_cancel_changes(driver, polars_server, polars_server_instance):
    driver.get(polars_server)
    time.sleep(2)
    
    # Make changes
    driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").click()
    driver.find_element(By.CSS_SELECTOR, "input").send_keys("test change")
    driver.find_element(By.CLASS_NAME, "header").click()
    time.sleep(1)
    
    # Add a new column
    driver.find_element(By.CLASS_NAME, "add-button").click()
    time.sleep(1)
    
    # Verify changes were made
    modified_cell_value = driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").text
    assert "test change" in modified_cell_value
    
    # Cancel changes
    cancel_button = driver.find_element(By.CLASS_NAME, "cancel-button")
    cancel_button.click()
    time.sleep(1)
    
    # Accept the confirmation dialog
    alert = SeleniumAlert(driver)
    alert.accept()
    time.sleep(1)
    
    # Verify changes were discarded
    toast = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "toast"))
    )
    assert "discarding changes" in toast.text.lower()
    
    # Convert both DataFrames to pandas for comparison since Polars doesn't have equals()
    original_pd = polars_server_instance.original_df
    current_pd = polars_server_instance.df
    assert original_pd.equals(current_pd)

def test_polars_type_preservation(polars_server_instance):
    """Test that numeric types are preserved when converting between Polars and Pandas"""
    original_df = pl.DataFrame({
        'int_col': [1, 2, 3],
        'float_col': [1.1, 2.2, 3.3],
        'str_col': ['a', 'b', 'c']
    })
    
    server = ShareServer(original_df)
    final_df = server.get_final_dataframe()
    
    # Check that the returned DataFrame is a Polars DataFrame
    assert isinstance(final_df, pl.DataFrame)
    
    # Check that the dtypes are preserved
    assert final_df['int_col'].dtype == pl.Int64
    assert final_df['float_col'].dtype == pl.Float64
    assert final_df['str_col'].dtype == pl.Utf8