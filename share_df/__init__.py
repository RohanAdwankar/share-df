import pandas as pd
import polars as pl
from typing import Union

__version__ = "0.1.0"
__all__ = ["pandaBear"]

def pandaBear(df: Union[pd.DataFrame, pl.DataFrame], use_iframe: bool = False) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Opens an interactive web editor for a pandas or polars DataFrame with authentication.
    
    Args:
        df (Union[pd.DataFrame, pl.DataFrame]): The DataFrame to edit.
        use_iframe (bool, optional): Whether to display the editor in an iframe (Google Colab only). Defaults to False.
        
    Returns:
        Union[pd.DataFrame, pl.DataFrame]: The edited DataFrame in the same type as input.
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

def _register_polars_extension():
    if not hasattr(pl.DataFrame, "pandaBear"):
        class PolarsBearAccessor:
            def __init__(self, polars_obj):
                self._obj = polars_obj
                
            def __call__(self, use_iframe: bool = False):
                modified_df = pandaBear(self._obj, use_iframe=use_iframe)
                self._obj.clear()
                for col in modified_df.columns:
                    self._obj.with_columns(modified_df[col])
                return None
        
        setattr(pl.DataFrame, "pandaBear", property(lambda self: PolarsBearAccessor(self)))

_register_polars_extension()