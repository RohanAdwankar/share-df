import pytest
import pandas as pd
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
def server(get_free_port):
   df = pd.DataFrame({'col1': [1,2,3], 'col2': ['a','b','c']})
   server = ShareServer(df)
   url, shutdown_event = server.serve(port=get_free_port)
   yield url
   shutdown_event.set()

@pytest.fixture
def driver(server):
    driver = webdriver.Chrome()
    yield driver
    driver.quit()

@pytest.fixture(scope="module") 
def server_instance(get_free_port):
   df = pd.DataFrame({'col1': [1,2,3], 'col2': ['a','b','c']})
   server = ShareServer(df)
   url, shutdown_event = server.serve(port=get_free_port)
   yield server
   shutdown_event.set()

def test_edit_cell(driver, server):
    driver.get(server)
    time.sleep(2)
    driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").click()
    driver.find_element(By.CSS_SELECTOR, "input").send_keys("new value")
    driver.find_element(By.CLASS_NAME, "header").click()
    time.sleep(2)
    assert driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").text == "1new value"

def test_add_column(driver, server):
   driver.get(server)
   time.sleep(2)
   
   driver.find_element(By.CLASS_NAME, "add-button").click()
   time.sleep(2)
   
   assert 'New Column' in driver.find_element(By.CSS_SELECTOR, ".tabulator-header").text

def test_add_row(driver, server):
   driver.get(server)
   time.sleep(2)
   initial_rows = len(driver.find_elements(By.CSS_SELECTOR, ".tabulator-row"))
   
   driver.find_elements(By.CLASS_NAME, "add-button")[1].click()
   time.sleep(2)
   
   final_rows = len(driver.find_elements(By.CSS_SELECTOR, ".tabulator-row"))
   assert final_rows == initial_rows + 1

def test_save_changes(driver, server):
   driver.get(server)
   time.sleep(2)
   
   driver.find_element(By.CLASS_NAME, "save-button").click()
   time.sleep(1)
   
   toast = driver.find_element(By.CLASS_NAME, "toast")
   assert "saved successfully" in toast.text.lower()

def test_rename_column(driver, server):
   driver.get(server)
   time.sleep(2)
   
   header = driver.find_element(By.CSS_SELECTOR, ".tabulator-col-title")
   header.click()
   input_elem = driver.find_element(By.CSS_SELECTOR, "input")
   input_elem.send_keys("Renamed")
   driver.find_element(By.CLASS_NAME, "header").click()
   time.sleep(2)
   
   assert "Renamed" in driver.find_element(By.CSS_SELECTOR, ".tabulator-header").text

def test_cancel_changes(driver, server, server_instance):
    driver.get(server)
    time.sleep(2)
    
    driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").click()
    driver.find_element(By.CSS_SELECTOR, "input").send_keys("test change")
    driver.find_element(By.CLASS_NAME, "header").click()
    time.sleep(1)
    
    driver.find_element(By.CLASS_NAME, "add-button").click()
    time.sleep(1)
    
    modified_cell_value = driver.find_element(By.CSS_SELECTOR, ".tabulator-cell").text
    assert "test change" in modified_cell_value
    
    cancel_button = driver.find_element(By.CLASS_NAME, "cancel-button")
    cancel_button.click()
    time.sleep(1)
    
    alert = SeleniumAlert(driver)
    alert.accept()
    time.sleep(1)
    
    toast = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "toast"))
    )
    assert "discarding changes" in toast.text.lower()    
    assert server_instance.df.equals(server_instance.original_df)