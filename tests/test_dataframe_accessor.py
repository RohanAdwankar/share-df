import pytest
import pandas as pd
from share_df import pandaBear

def test_accessor_registration():
    """Test that the pandaBear accessor is properly registered"""
    df = pd.DataFrame()
    assert hasattr(df, 'pandaBear')
    assert callable(df.pandaBear)

def test_accessor_initialization(sample_df):
    """Test that the accessor initializes correctly"""
    accessor = sample_df.pandaBear
    assert hasattr(accessor, '_obj')
    assert accessor._obj is sample_df

def test_accessor_with_empty_dataframe(empty_df):
    """Test that the accessor works with empty DataFrame"""
    assert hasattr(empty_df, 'pandaBear')
    assert callable(empty_df.pandaBear)