# tests/test_server.py
import pytest
from fastapi.testclient import TestClient
from share_df.server import ShareServer
import pandas as pd
import json

@pytest.fixture
def test_server(sample_df):
    """Create a test server instance"""
    server = ShareServer(sample_df)
    return server

@pytest.fixture
def test_client(test_server):
    """Create a test client"""
    return TestClient(test_server.app)

def test_root_endpoint(test_client):
    """Test that the root endpoint returns HTML"""
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert "DataFrame Editor" in response.text

def test_data_endpoint(test_client, sample_df):
    """Test that the data endpoint returns correct DataFrame data"""
    response = test_client.get("/data")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_df)
    assert all(key in data[0] for key in sample_df.columns)

def test_update_data_endpoint(test_client):
    """Test updating DataFrame data"""
    new_data = {
        "data": [
            {"Name": "John", "Age": 26, "City": "Boston", "Salary": 55000},
            {"Name": "Alice", "Age": 31, "City": "London", "Salary": 65000}
        ]
    }
    response = test_client.post(
        "/update_data",
        json=new_data
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_shutdown_endpoint(test_client):
    """Test shutdown endpoint"""
    response = test_client.post("/shutdown")
    assert response.status_code == 200
    assert response.json()["status"] == "shutting down"

async def test_server_serve_method(test_server):
    """Test that serve method returns correct URL and shutdown event"""
    url, shutdown_event = test_server.serve(host="127.0.0.1", port=8001)
    assert url == "http://localhost:8001"
    assert hasattr(shutdown_event, 'set')
    assert hasattr(shutdown_event, 'wait')
    shutdown_event.set()  # Clean up

def test_server_initialization_with_empty_df(empty_df):
    """Test server initialization with empty DataFrame"""
    server = ShareServer(empty_df)
    assert isinstance(server.df, pd.DataFrame)
    assert len(server.df) == 0

@pytest.mark.skip(reason="Requires manual input for email")
def test_full_pandabear_function(sample_df):
    """Test the main pandaBear function (skipped by default as it requires input)"""
    from share_df import pandaBear
    result_df = pandaBear(sample_df)
    assert isinstance(result_df, pd.DataFrame)