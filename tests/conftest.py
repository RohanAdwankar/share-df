import pytest
import pandas as pd

@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing"""
    return pd.DataFrame({
        'Name': ['John', 'Alice', 'Bob'],
        'Age': [25, 30, 35],
        'City': ['New York', 'London', 'Paris'],
        'Salary': [50000, 60000, 75000]
    })

@pytest.fixture
def empty_df():
    """Create an empty DataFrame for testing edge cases"""
    return pd.DataFrame()