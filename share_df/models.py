from pydantic import BaseModel
from typing import List, Dict, Any

class DataUpdate(BaseModel):
    data: List[Dict[Any, Any]]