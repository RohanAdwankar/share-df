from pydantic import BaseModel
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

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

class VersionChange(BaseModel):
    id: str
    timestamp: float  # Unix timestamp
    user_id: str
    user_name: str
    user_color: str
    change_type: str  # "cell_edit", "add_row", "add_column", "column_rename", etc.
    details: Dict[str, Any]  # Type-specific details about the change

class VersionSnapshot(BaseModel):
    id: str
    timestamp: float
    changes: List[VersionChange]
    interval_start: float  # Start of 5-minute interval
    interval_end: float    # End of 5-minute interval