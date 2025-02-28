import warnings
import pandas as pd
import polars as pl
from typing import Union

warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

__version__ = "0.1.0"
__all__ = ["pandaBear"]

def pandaBear(df: Union[pd.DataFrame, pl.DataFrame], use_iframe: bool = False, collaborative: bool = True, share_with: Union[str, list] = None, log_level: str = "CRITICAL", local: bool = False, strict_dtype: bool = True) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Opens an interactive web editor for a pandas or polars DataFrame with authentication.
    
    Args:
        df (Union[pd.DataFrame, pl.DataFrame]): The DataFrame to edit.
        use_iframe (bool, optional): Whether to display the editor in an iframe (Google Colab only). Defaults to False.
        collaborative (bool, optional): Whether to enable real-time collaboration features. Defaults to False.
        share_with (Union[str, list], optional): Email(s) to share the editor with (requires collaborative=True). Defaults to None.
        log_level (str, optional): Logging level. Defaults to "CRITICAL".
        local (bool, optional): Whether to run in local mode without ngrok. Defaults to False.
        strict_dtype (bool, optional): Whether to enforce strict dtype checking. Defaults to True.
        
    Returns:
        Union[pd.DataFrame, pl.DataFrame]: The edited DataFrame in the same type as input.
    """
    from .server import start_editor
    return start_editor(df, use_iframe=use_iframe, collaborative=collaborative, share_with=share_with, log_level=log_level, local=local, strict_dtype=strict_dtype)

@pd.api.extensions.register_dataframe_accessor("pandaBear")
class PandaBearAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj
        
    def __call__(self, use_iframe: bool = False, collaborative: bool = False, share_with: Union[str, list] = None, log_level: str = "CRITICAL", local: bool = False, strict_dtype: bool = True):
        self._obj.update(pandaBear(self._obj, use_iframe=use_iframe, collaborative=collaborative, share_with=share_with, log_level=log_level, local=local, strict_dtype=strict_dtype))
        return None

def _register_polars_extension():
    if not hasattr(pl.DataFrame, "pandaBear"):
        class PolarsBearAccessor:
            def __init__(self, polars_obj):
                self._obj = polars_obj
                
            def __call__(self, use_iframe: bool = False, collaborative: bool = False, share_with: Union[str, list] = None, log_level: str = "CRITICAL", local: bool = False, strict_dtype: bool = True):
                modified_df = pandaBear(self._obj, use_iframe=use_iframe, collaborative=collaborative, share_with=share_with, log_level=log_level, local=local, strict_dtype=strict_dtype)
                self._obj.clear()
                for col in modified_df.columns:
                    self._obj.with_columns(modified_df[col])
                return None
        
        setattr(pl.DataFrame, "pandaBear", property(lambda self: PolarsBearAccessor(self)))

_register_polars_extension()