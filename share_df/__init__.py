import pandas as pd

__version__ = "0.1.0"
__all__ = ["pandaBear"]

def pandaBear(df: pd.DataFrame) -> pd.DataFrame:
    """
    Opens an interactive web editor for a pandas DataFrame with authentication.
    
    Args:
        df (pd.DataFrame): The DataFrame to edit
        
    Returns:
        pd.DataFrame: The edited DataFrame
    """
    from .server import start_editor
    return start_editor(df)

@pd.api.extensions.register_dataframe_accessor("pandaBear")
class PandaBearAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj
        
    def __call__(self):
        self._obj.update(pandaBear(self._obj))
        return None