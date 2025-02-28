import pandas as pd
import polars as pl
from typing import Union

__version__ = "0.1.0"
__all__ = ["pandaBear"]

def pandaBear(df: Union[pd.DataFrame, pl.DataFrame], use_iframe: bool = False, collaborative: bool = True, share_with: Union[str, list] = None, log_level: str = "CRITICAL",local: bool = False) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Opens an interactive web editor for a pandas or polars DataFrame with authentication.
    
    Args:
        df (Union[pd.DataFrame, pl.DataFrame]): The DataFrame to edit.
        use_iframe (bool, optional): Whether to display the editor in an iframe (Google Colab only). Defaults to False.
        collaborative (bool, optional): Whether to enable real-time collaboration features. Defaults to False.
        share_with (Union[str, list], optional): Email(s) to share the editor with (requires collaborative=True). Defaults to None.
        
    Returns:
        Union[pd.DataFrame, pl.DataFrame]: The edited DataFrame in the same type as input.
    """
    from .server import start_editor
    return start_editor(df, use_iframe=use_iframe, collaborative=collaborative, share_with=share_with, log_level=log_level, local=local)

@pd.api.extensions.register_dataframe_accessor("pandaBear")
class PandaBearAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj
        
    def __call__(self, use_iframe: bool = False, collaborative: bool = False, share_with: Union[str, list] = None, log_level: str = "CRITICAL", local: bool = False):
        self._obj.update(pandaBear(self._obj, use_iframe=use_iframe, collaborative=collaborative, share_with=share_with, log_level=log_level, local=local))
        return None

def _register_polars_extension():
    if not hasattr(pl.DataFrame, "pandaBear"):
        class PolarsBearAccessor:
            def __init__(self, polars_obj):
                self._obj = polars_obj
                
            def __call__(self, use_iframe: bool = False, collaborative: bool = False, share_with: Union[str, list] = None, log_level: str = "CRITICAL", local: bool = False):
                modified_df = pandaBear(self._obj, use_iframe=use_iframe, collaborative=collaborative, share_with=share_with, log_level=log_level, local=local)
                self._obj.clear()
                for col in modified_df.columns:
                    self._obj.with_columns(modified_df[col])
                return None
        
        setattr(pl.DataFrame, "pandaBear", property(lambda self: PolarsBearAccessor(self)))

_register_polars_extension()