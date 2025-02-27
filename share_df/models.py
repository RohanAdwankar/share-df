from pydantic import BaseModel
from typing import Dict, List, Any, Optional

class DataUpdate(BaseModel):
    data: List[Dict[str, Any]]

class Cursor(BaseModel):
    row: int = -1
    col: int = -1

class CollaboratorInfo(BaseModel):
    id: str
    name: str
    color: str
    cursor: Optional[Dict[str, int]] = None
    email: Optional[str] = None