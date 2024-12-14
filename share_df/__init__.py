import pandas as pd

__version__ = "0.1.0"
__all__ = ["pandaBear"]

def pandaBear(df: pd.DataFrame, use_iframe: bool = False) -> pd.DataFrame:
    """
    Opens an interactive web editor for a pandas DataFrame with authentication.
    
    Args:
        df (pd.DataFrame): The DataFrame to edit.
        use_iframe (bool, optional): Whether to display the editor in an iframe (Google Colab only). Defaults to False.
        
    Returns:
        pd.DataFrame: The edited DataFrame.
    """
    from .server import start_editor
    return start_editor(df, use_iframe=use_iframe)

@pd.api.extensions.register_dataframe_accessor("pandaBear")
class PandaBearAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj
        
    def __call__(self, use_iframe: bool = False):
        self._obj.update(pandaBear(self._obj, use_iframe=use_iframe))
        return None