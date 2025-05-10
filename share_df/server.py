import time
import threading
import uvicorn
import pandas as pd
import polars as pl
import logging
import json
import uuid
import asyncio
import numpy as np
from datetime import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Union, Dict, List
from .models import DataUpdate, CollaboratorInfo, VersionChange, VersionSnapshot
import os
import ngrok
from dotenv import load_dotenv
import json
import uuid

logger = logging.getLogger("share_df")

class ShareServer:
    def __init__(self, df: Union[pd.DataFrame, pl.DataFrame], collaborative_mode: bool = True, test_mode: bool = False, log_level: str = "CRITICAL", strict_dtype: bool = True):
        # Configure logging level
        log_level = log_level.upper()
        numeric_level = getattr(logging, log_level, logging.CRITICAL)
        logger.setLevel(numeric_level)
        
        # Add a handler if none exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        self.app = FastAPI()
        self.shutdown_event = threading.Event()
        self.collaborative_mode = collaborative_mode
        self.test_mode = test_mode
        self.active_connections: Dict[str, WebSocket] = {}
        self.collaborators: Dict[str, CollaboratorInfo] = {}
        self.cell_editors: Dict[str, str] = {}  # Maps cell ID to user ID of current editor
        self.strict_dtype = strict_dtype
        
        self.added_columns = []
        self.added_rows_count = 0
        self.current_data = []
        
        # Version tracking - store changes grouped by 5min intervals
        self.version_changes: List[VersionChange] = []
        self.version_snapshots: List[VersionSnapshot] = []
        self.version_history_enabled = collaborative_mode  # Only enable in collaborative mode
        self.current_snapshot_id = None
        self.snapshot_interval_seconds = 300  # 5 minute intervals
        self.changes_made = False  # Track if any changes have been made
        
        if isinstance(df, pl.DataFrame):
            self.original_type = "polars"
            self.df = df.to_pandas()
        else:
            self.original_type = "pandas"
            self.df = df
            
        self.original_df = self.df.copy()
        
        base_dir = Path(__file__).resolve().parent
        templates_dir = base_dir / "static" / "templates"
        static_dir = base_dir / "static"
        
        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
        
        self.templates = Jinja2Templates(directory=templates_dir)
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.setup_routes()
        
        # Add message tracking for deduplication
        self.recent_messages = {}
    
    def debug_server_status(self):
        """Print debug information about the server state"""
        import sys
        logger.debug(f"Server Debug Information:")
        logger.debug(f"  Python Version: {sys.version}")
        logger.debug(f"  Collaborative Mode: {self.collaborative_mode}")
        logger.debug(f"  Test Mode: {self.test_mode}")
        logger.debug(f"  DataFrame Type: {self.original_type}")
        logger.debug(f"  DataFrame Shape: {self.df.shape}")
        logger.debug(f"  DataFrame Columns: {list(self.df.columns)}")
        logger.debug(f"  DataFrame First Row: {self.df.iloc[0].to_dict() if len(self.df) > 0 else 'Empty'}")
        logger.debug(f"  Active Connections: {len(self.active_connections)}")
        logger.debug(f"  Active Collaborators: {len(self.collaborators)}")
    
    def setup_routes(self):
        @self.app.get("/")
        async def root(request: Request):
            """Root endpoint that renders the editor template"""
            if self.test_mode:
                logger.debug("Rendering template in test mode")
            
            # For FastAPI 0.95.0+, we need to pass request as first argument
            try:
                # Try the newer API style
                return self.templates.TemplateResponse(
                    request=request,
                    name="editor.html",
                    context={
                        "collaborative": self.collaborative_mode,
                        "test_mode": self.test_mode
                    }
                )
            except TypeError:
                # Fall back to older API style
                return self.templates.TemplateResponse(
                    "editor.html",
                    {
                        "request": request,
                        "collaborative": self.collaborative_mode,
                        "test_mode": self.test_mode
                    }
                )
            
        @self.app.get("/data")
        async def get_data():
            """Get DataFrame data with test mode handling"""
            # In test mode, add debug info
            if self.test_mode:
                self.debug_server_status()
            
            # Ensure the dataframe is not empty
            if self.df.empty:
                logger.warning("Warning: DataFrame is empty!")
                # Return a minimal dummy dataframe for testing
                if self.test_mode:
                    logger.debug("Using dummy data in test mode")
                    return [{"col1": 1, "col2": "test"}]
                else:
                    return []
            
            # Convert the DataFrame to records
            data = self.df.to_dict(orient='records')
            self.current_data = data
            
            # Add debug info for test mode
            if self.test_mode:
                logger.debug(f"Sending {len(data)} records:")
                if len(data) > 0:
                    logger.debug(f"  First record: {data[0]}")
            else:
                logger.debug(f"Sending data: {len(data)} records")
            
            return JSONResponse(content=data)
            
        @self.app.post("/update_data")
        async def update_data(data_update: DataUpdate):
            if len(data_update.data) > 1_000_000:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Dataset too large"}
                )
            
            updated_df = pd.DataFrame(data_update.data)
            if self.original_type == "polars":
                self.df = updated_df
            else:
                self.df = updated_df
            
            self.current_data = data_update.data
            
            original_rows = len(self.original_df)
            current_rows = len(updated_df)
            if current_rows > original_rows:
                self.added_rows_count = current_rows - original_rows
                
            logger.info("Updated DataFrame")
            return {"status": "success"}
            
        @self.app.post("/shutdown")
        async def shutdown():
            final_df = self.get_final_dataframe()
            self.shutdown_event.set()
            return JSONResponse(
                status_code=200,
                content={"status": "shutting down"}
            )
        
        @self.app.post("/cancel")
        async def cancel():
            self.df = self.original_df.copy()
            self.shutdown_event.set()
            return JSONResponse(
                status_code=200,
                content={"status": "canceling"}
            )
        
        # Add this new endpoint for saving in collaborative mode
        @self.app.post("/save_and_continue")
        async def save_and_continue(data_update: DataUpdate):
            """Save data without shutting down - for collaborative mode"""
            if len(data_update.data) > 1_000_000:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Dataset too large"}
                )
            
            updated_df = pd.DataFrame(data_update.data)
            if self.original_type == "polars":
                self.df = updated_df
            else:
                self.df = updated_df
                
            logger.info("Updated DataFrame from collaborative save")
            
            # Broadcast data update to all users
            if self.collaborative_mode:
                await self.broadcast({
                    "type": "data_sync",
                    "message": "Data has been updated by another user"
                })
            
            return {"status": "success", "message": "Data saved without shutting down"}

        @self.app.get("/version_history")
        async def get_version_history():
            """Get the current version history"""
            if not self.version_history_enabled:
                return {"error": "Version history is not enabled"}
            
            return self.get_version_history()
            
        @self.app.post("/restore_version")
        async def restore_version(request: Request):
            """Restore to a specific version"""
            if not self.version_history_enabled:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Version history is not enabled"}
                )
            
            data = await request.json()
            snapshot_id = data.get("snapshot_id")
            change_id = data.get("change_id")
            
            if not snapshot_id and not change_id:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Either snapshot_id or change_id must be provided"}
                )
            
            success = await self.restore_version(snapshot_id, change_id)
            
            if success:
                return {"status": "success"}
            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Failed to restore version"}
                )

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            user_id = str(uuid.uuid4())
            user_name = f"User {user_id[:6]}"
            self.active_connections[user_id] = websocket
            
            try:
                logger.info(f"New WebSocket connection: {user_id}")
                
                if not self.current_data or len(self.current_data) != len(self.df):
                    self.current_data = self.df.to_dict(orient='records')
                
                # Send current state to the new user
                await websocket.send_json({
                    "type": "init",
                    "userId": user_id,
                    "collaborators": [collab.dict() for collab in self.collaborators.values()],
                    "addedColumns": self.added_columns,  # Send list of added columns to new users
                    "currentData": self.current_data,    # Send current data state
                    "addedRows": self.added_rows_count,  # Send info about added rows
                    "versionSnapshots": [s.dict() for s in self.version_snapshots] if self.version_history_enabled else [],
                    "versionChanges": [c.dict() for c in self.version_changes] if self.version_history_enabled else []
                })
                
                # Notify other users about the new user
                await self.broadcast({
                    "type": "user_joined",
                    "userId": user_id,
                    "name": user_name
                }, exclude=user_id)
                
                while True:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    message_type = message.get("type", "")
                    
                    logger.debug(f"Received message from {user_id}: {message_type}")
                    
                    # Add debug ping handler
                    if message_type == "debug_ping":
                        timestamp = message.get("timestamp", 0)
                        now = int(time.time() * 1000)
                        latency = now - timestamp
                        
                        logger.debug(f"Debug ping from {user_id}: latency {latency}ms")
                        
                        # Send pong response
                        await websocket.send_json({
                            "type": "debug_pong",
                            "timestamp": timestamp,
                            "server_time": now,
                            "latency": latency
                        })
                        continue
                    
                    if message_type == "update_user":
                        # Update user info (name, color, cursor position)
                        self.collaborators[user_id] = CollaboratorInfo(
                            id=user_id,
                            name=message.get("name", user_name),
                            color=message.get("color", "#3b82f6"),
                            cursor=message.get("cursor", {"row": -1, "col": -1}),
                            email=message.get("email", "")
                        )
                        
                        # Broadcast user info update to everyone
                        await self.broadcast({
                            "type": "user_update",
                            "user": self.collaborators[user_id].dict()
                        })
                        
                    elif message_type == "cell_focus":
                        # User focused a cell
                        cell_id = message.get("cellId")
                        self.cell_editors[cell_id] = user_id
                        
                        # Broadcast focus info to everyone
                        await self.broadcast({
                            "type": "cell_focus",
                            "cellId": cell_id,
                            "userId": user_id
                        })
                        
                    elif message_type == "cell_blur":
                        # User left a cell
                        cell_id = message.get("cellId")
                        if cell_id in self.cell_editors and self.cell_editors[cell_id] == user_id:
                            self.cell_editors.pop(cell_id)
                            
                        # Broadcast blur info to everyone
                        await self.broadcast({
                            "type": "cell_blur",
                            "cellId": cell_id,
                            "userId": user_id
                        })
                        
                    elif message_type == "cell_edit":
                        await self.handle_cell_edit(message, websocket)
                        
                    elif message_type == "cursor_position":
                        # User moved to a specific cell - this replaces cursor_move with cell tracking
                        position = message.get("position", {})
                        if user_id in self.collaborators and position:
                            # Update user's cursor position
                            self.collaborators[user_id].cursor = position
                            
                            # Broadcast to everyone else
                            await self.broadcast({
                                "type": "cursor_position",
                                "position": position,
                                "userId": user_id
                            }, exclude=user_id)
                        
                    elif message_type == "table_structure":
                        # User changed table structure (added columns, rows, etc)
                        columns = message.get("columns", [])
                        row_count = message.get("rowCount", 0)
                        
                        # Broadcast to everyone else
                        await self.broadcast({
                            "type": "table_structure",
                            "columns": columns,
                            "rowCount": row_count,
                            "userId": user_id
                        }, exclude=user_id)
                        
                    elif message_type == "column_reorder":
                        # User reordered columns
                        columns = message.get("columns", [])
                        
                        # Broadcast to everyone else
                        await self.broadcast({
                            "type": "column_reorder",
                            "columns": columns,
                            "userId": user_id
                        }, exclude=user_id)
                    
                    elif message_type == "add_column":
                        # User added a column
                        column_name = message.get("columnName", "")
                        operation_id = message.get("operationId", "")
                        
                        logger.info(f"User {user_id} added column: {column_name}")
                        
                        # Store the added column
                        if column_name and column_name not in self.added_columns:
                            self.added_columns.append(column_name)
                            
                            # Also ensure the column exists in our DataFrame
                            if column_name not in self.df.columns:
                                self.df[column_name] = ""
                                
                            # Update current_data with the new column
                            for row in self.current_data:
                                if column_name not in row:
                                    row[column_name] = ""
                                    
                            # Track the change for version history
                            if self.version_history_enabled:
                                self.track_version_change(
                                    user_id=user_id,
                                    change_type="add_column",
                                    details={
                                        "column_name": column_name
                                    }
                                )
                        
                        # Broadcast to everyone
                        await self.broadcast({
                            "type": "add_column",
                            "columnName": column_name,
                            "userId": user_id,
                            "operationId": operation_id
                        })
                        
                    elif message_type == "add_row":
                        # User added a row
                        row_id = message.get("rowId", -1)
                        operation_id = message.get("operationId", "")
                        
                        logger.info(f"User {user_id} added row at position: {row_id}")
                        
                        # Update our count of added rows
                        self.added_rows_count += 1
                        
                        # Create a new empty row in our DataFrame
                        if len(self.df) > 0:
                            empty_row = pd.Series("", index=self.df.columns)
                            self.df = pd.concat([self.df, pd.DataFrame([empty_row])], ignore_index=True)
                            
                            # Also update current_data
                            new_row = {column: "" for column in self.df.columns}
                            self.current_data.append(new_row)
                            
                            # Track the change for version history
                            if self.version_history_enabled:
                                self.track_version_change(
                                    user_id=user_id,
                                    change_type="add_row",
                                    details={
                                        "row_id": row_id
                                    }
                                )
                        
                        # Broadcast to everyone
                        await self.broadcast({
                            "type": "add_row",
                            "rowId": row_id,
                            "userId": user_id,
                            "operationId": operation_id
                        })
                    
                    elif message_type == "user_finished":
                        # User is leaving but server continues for others
                        logger.info(f"User {user_id} is finishing their session")
                        
                        # Let everyone know this user is leaving
                        await self.broadcast({
                            "type": "user_finished",
                            "userId": user_id,
                            "name": self.collaborators[user_id].name if user_id in self.collaborators else user_name
                        })
            
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {user_id}")
                # Remove disconnected user
                if user_id in self.active_connections:
                    del self.active_connections[user_id]
                
                user_name = self.collaborators[user_id].name if user_id in self.collaborators else user_name
                
                if user_id in self.collaborators:
                    del self.collaborators[user_id]
                
                # Remove them from cell editors
                cells_to_remove = [cell_id for cell_id, editor_id in self.cell_editors.items() if editor_id == user_id]
                for cell_id in cells_to_remove:
                    del self.cell_editors[cell_id]
                    
                # Notify others about the disconnection
                await self.broadcast({
                    "type": "user_left",
                    "userId": user_id,
                    "name": user_name
                })
            except Exception as e:
                logger.error(f"WebSocket error for {user_id}: {e}")
                if user_id in self.active_connections:
                    del self.active_connections[user_id]
                if user_id in self.collaborators:
                    del self.collaborators[user_id]
    
    async def handle_cell_edit(self, message, websocket):
        """Handle a cell edit message from a client"""
        # Extract message data
        row_id = message.get("rowId")
        column = message.get("column")
        value = message.get("value")
        user_id = message.get("userId")
        old_value = message.get("oldValue", "")
        
        # Validate the data
        if row_id is None or column is None:
            return
        
        try:
            row_index = int(row_id)
            
            # Check if the column exists
            if column not in self.df.columns:
                return
            
            # DTYPE VALIDATION: Check if the value is compatible with column dtype
            if self.strict_dtype:
                col_dtype = self.df[column].dtype
                try:
                    # Try to convert the value to the column's dtype
                    converted_value = self._convert_value_to_dtype(value, col_dtype)
                    value = converted_value
                except (ValueError, TypeError):
                    # Send error message to the client
                    await self.send_dtype_error(websocket, row_id, column, value, col_dtype)
                    return
            
            # Apply the edit
            self.df.at[row_index, column] = value
            
            # Forward message to all other clients
            await self.broadcast(message)
            
            # Track the change for version history
            if user_id and self.version_history_enabled:
                self.track_version_change(
                    user_id=user_id,
                    change_type="cell_edit",
                    details={
                        "row": row_id,
                        "column": column,
                        "old_value": old_value,
                        "new_value": str(value)
                    }
                )
            
            # Mark that changes have been made
            self.changes_made = True
            
        except Exception as e:
            logger.error(f"Error handling cell edit: {e}")
    
    def _convert_value_to_dtype(self, value, dtype):
        """Convert a value to the specified dtype"""
        if pd.api.types.is_integer_dtype(dtype):
            if value == '' or value is None:
                return pd.NA if hasattr(pd, 'NA') else np.nan
            return int(value)
        elif pd.api.types.is_float_dtype(dtype):
            if value == '' or value is None:
                return np.nan
            return float(value)
        elif pd.api.types.is_bool_dtype(dtype):
            if value == '' or value is None:
                return pd.NA if hasattr(pd, 'NA') else np.nan
            if isinstance(value, str):
                value = value.lower()
                if value in ('true', 'yes', '1', 'y', 't'):
                    return True
                elif value in ('false', 'no', '0', 'n', 'f'):
                    return False
            return bool(value)
        elif pd.api.types.is_datetime64_dtype(dtype):
            if value == '' or value is None:
                return pd.NaT
            return pd.to_datetime(value)
        else:
            # Default: convert to string for object/string types
            return str(value) if value is not None else value
    
    async def send_dtype_error(self, websocket, row_id, column, value, dtype):
        """Send a data type validation error message to the client"""
        error_message = {
            "type": "dtype_error",
            "rowId": row_id,
            "column": column,
            "value": value,
            "expected_dtype": str(dtype),
            "message": f"Value '{value}' is not compatible with column type {dtype}"
        }
        await websocket.send_json(error_message)
    
    async def broadcast(self, message: dict, exclude: str = None):
        """Broadcast a message to all connected clients except the excluded one"""
        msg_type = message.get('type', 'unknown')
        client_count = len(self.active_connections)
        extra_info = ""
        
        # Generate a server message ID for this broadcast
        message["server_msg_id"] = f"{msg_type}_{time.time()}_{uuid.uuid4().hex[:6]}"
        
        # Check if this is a duplicate message (within 300ms)
        message_key = self._get_message_signature(message)
        current_time = time.time()
        
        if message_key in self.recent_messages:
            last_time = self.recent_messages[message_key]
            if current_time - last_time < 0.3:  # 300ms
                logger.debug(f"Skipping duplicate message: {message_key}")
                return
                
        # Update message timestamp
        self.recent_messages[message_key] = current_time
        
        # Clean up old messages (older than 5 seconds)
        self.recent_messages = {k: v for k, v in self.recent_messages.items() 
                               if current_time - v < 5.0}
        
        if msg_type == 'cell_edit':
            extra_info = f" - Cell [{message.get('rowId')}, {message.get('column')}] = {message.get('value')}"
        
        logger.info(f"Broadcasting '{msg_type}'{extra_info} to {client_count} client(s)" + 
                    (f" (excluding {exclude})" if exclude else ""))
        
        sent_count = 0
        for client_id, connection in self.active_connections.items():
            if exclude is None or client_id != exclude:
                try:
                    await connection.send_json(message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error broadcasting to {client_id}: {e}")
        
        logger.debug(f"Message sent to {sent_count}/{client_count} client(s)")

    def _get_message_signature(self, message: dict) -> str:
        """Generate a unique signature for a message to detect duplicates"""
        msg_type = message.get('type', '')
        
        if msg_type == 'cell_edit':
            return f"cell_edit:{message.get('userId')}:{message.get('rowId')}:{message.get('column')}:{message.get('value')}"
        elif msg_type == 'add_column':
            return f"add_column:{message.get('userId')}:{message.get('columnName')}"
        elif msg_type == 'add_row':
            return f"add_row:{message.get('userId')}:{message.get('rowId')}"
        
        # For other message types, use type + userId
        return f"{msg_type}:{message.get('userId', '')}"
        
    def track_version_change(self, user_id: str, change_type: str, details: dict):
        """Track a change for version history"""
        if not self.version_history_enabled:
            return
            
        # Get user info
        user_info = self.collaborators.get(user_id)
        if not user_info:
            # Default values if collaborator info not found
            user_name = f"User {user_id[:6]}"
            user_color = "#3b82f6"
        else:
            user_name = user_info.name
            user_color = user_info.color
            
        # Create change record
        change = VersionChange(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            user_id=user_id,
            user_name=user_name,
            user_color=user_color,
            change_type=change_type,
            details=details
        )
        
        # Add to changes list
        self.version_changes.append(change)
        
        # Check if we need to create a new snapshot
        self._check_snapshot_interval()
        
        # Broadcast version update to all clients
        asyncio.create_task(self._broadcast_version_update(change))
        
    async def _broadcast_version_update(self, change):
        """Broadcast version change to all clients"""
        await self.broadcast({
            "type": "version_change",
            "change": change.dict()
        })
        
    def _check_snapshot_interval(self):
        """Check if we need to create a new snapshot based on time intervals"""
        current_time = time.time()
        
        # Calculate the 5-minute interval this change falls into
        interval_start = current_time - (current_time % self.snapshot_interval_seconds)
        interval_end = interval_start + self.snapshot_interval_seconds
        
        # Check if we need to create a new snapshot
        if not self.current_snapshot_id or len([s for s in self.version_snapshots if s.interval_start == interval_start]) == 0:
            # Create a new snapshot for this interval
            snapshot_id = str(uuid.uuid4())
            self.current_snapshot_id = snapshot_id
            
            # Find changes in this interval
            interval_changes = [c for c in self.version_changes 
                               if interval_start <= c.timestamp < interval_end]
            
            # Create the snapshot
            snapshot = VersionSnapshot(
                id=snapshot_id,
                timestamp=current_time,
                changes=interval_changes,
                interval_start=interval_start,
                interval_end=interval_end
            )
            
            # Add to snapshots list
            self.version_snapshots.append(snapshot)
            
            # Broadcast snapshot to clients
            asyncio.create_task(self._broadcast_snapshot_update(snapshot))
    
    async def _broadcast_snapshot_update(self, snapshot):
        """Broadcast new snapshot to all clients"""
        await self.broadcast({
            "type": "version_snapshot",
            "snapshot": {
                "id": snapshot.id,
                "timestamp": snapshot.timestamp,
                "interval_start": snapshot.interval_start,
                "interval_end": snapshot.interval_end,
                "change_count": len(snapshot.changes)
            }
        })
        
    def get_version_history(self):
        """Get the complete version history"""
        return {
            "snapshots": [s.dict() for s in self.version_snapshots],
            "changes": [c.dict() for c in self.version_changes]
        }
        
    async def restore_version(self, snapshot_id=None, change_id=None):
        """Restore the dataframe to a specific version"""
        # Implementation depends on how we store the actual data
        # This would require storing actual dataframe snapshots or
        # implementing undo/redo functionality
        if snapshot_id:
            # Find the snapshot
            snapshot = next((s for s in self.version_snapshots if s.id == snapshot_id), None)
            if not snapshot:
                logger.error(f"Snapshot {snapshot_id} not found")
                return False
                
            # Reset to original DataFrame
            self.df = self.original_df.copy()
            self.current_data = self.df.to_dict(orient='records')
            
            # Apply all changes up to this snapshot's last change
            if snapshot.changes:
                last_change_time = max(c.timestamp for c in snapshot.changes)
                valid_changes = [c for c in self.version_changes if c.timestamp <= last_change_time]
                
                # Apply these changes in order
                for change in valid_changes:
                    self._apply_change(change)
                    
            # Broadcast the restore action
            await self.broadcast({
                "type": "version_restored",
                "snapshot_id": snapshot_id,
                "message": f"DataFrame restored to version from {datetime.fromtimestamp(snapshot.timestamp).strftime('%H:%M:%S')}"
            })
            return True
        
        elif change_id:
            # Find the change
            change = next((c for c in self.version_changes if c.id == change_id), None)
            if not change:
                logger.error(f"Change {change_id} not found")
                return False
            
            # Handle undoing a specific change
            if change.change_type == "cell_edit":
                row_id = change.details.get("row")
                column = change.details.get("column")
                old_value = change.details.get("old_value")
                
                if row_id is not None and column is not None and old_value is not None:
                    try:
                        row_index = int(row_id)
                        self.df.at[row_index, column] = old_value
                        
                        # Update current_data
                        if 0 <= row_index < len(self.current_data):
                            self.current_data[row_index][column] = old_value
                            
                        # Broadcast the change
                        await self.broadcast({
                            "type": "cell_edit",
                            "rowId": row_id,
                            "column": column,
                            "value": old_value,
                            "userId": "system",
                            "fromRevert": True,
                            "changeId": change_id
                        })
                        
                        return True
                    except Exception as e:
                        logger.error(f"Error reverting cell edit: {e}")
                        return False
            
            # Other change types would be handled here
            return False
            
        return False
    
    def _apply_change(self, change):
        """Apply a single change to the current dataframe"""
        try:
            if change.change_type == "cell_edit":
                row_id = change.details.get("row")
                column = change.details.get("column")
                new_value = change.details.get("new_value")
                
                if row_id is not None and column is not None and new_value is not None:
                    row_index = int(row_id)
                    
                    # Make sure the column exists
                    if column not in self.df.columns:
                        return False
                        
                    # Apply the edit
                    self.df.at[row_index, column] = new_value
                    
                    # Update current_data
                    if 0 <= row_index < len(self.current_data):
                        self.current_data[row_index][column] = new_value
                
            elif change.change_type == "add_column":
                column_name = change.details.get("column_name")
                
                if column_name and column_name not in self.df.columns:
                    self.df[column_name] = ""
                    
                    # Update current_data
                    for row in self.current_data:
                        if column_name not in row:
                            row[column_name] = ""
                            
                    # Add to our tracking list
                    if column_name not in self.added_columns:
                        self.added_columns.append(column_name)
            
            elif change.change_type == "add_row":
                # Add a new empty row
                if len(self.df) > 0:
                    empty_row = pd.Series("", index=self.df.columns)
                    self.df = pd.concat([self.df, pd.DataFrame([empty_row])], ignore_index=True)
                    
                    # Update current_data
                    new_row = {column: "" for column in self.df.columns}
                    self.current_data.append(new_row)
                    
                    # Update tracking
                    self.added_rows_count += 1
                    
            return True
        except Exception as e:
            logger.error(f"Error applying change: {e}")
            return False

    def get_final_dataframe(self):
        """Convert the DataFrame back to its original type before returning"""
        if self.original_type == "polars":
            return pl.from_pandas(self.df)
        return self.df

    def serve(self, host="0.0.0.0", port=8000, use_iframe=False):
        try:
            from google.colab import output
            # If that works we're in Colab
            if use_iframe:
                output.serve_kernel_port_as_iframe(port)
            else:
                output.serve_kernel_port_as_window(port)
            server_config = uvicorn.Config(
                self.app,
                host=host,
                port=port,
                log_level="critical"
            )
            server = uvicorn.Server(server_config)
            
            server_thread = threading.Thread(
                target=server.run,
                daemon=True
            )
            server_thread.start()
            time.sleep(2)
            #None for url since we're using Colab's output
            return None, self.shutdown_event
        except ImportError:
            # Not in Colab
            
            # Check if we're in a Jupyter environment
            is_jupyter = False
            try:
                from IPython import get_ipython
                if get_ipython() is not None:
                    is_jupyter = True
            except ImportError:
                pass
                
            # Configure server - disable uvloop in Jupyter
            server_config = uvicorn.Config(
                self.app,
                host=host,
                port=port,
                log_level="critical",
                loop="asyncio" if is_jupyter else "auto"  # Force standard asyncio loop in Jupyter
            )
            server = uvicorn.Server(server_config)
            
            server_thread = threading.Thread(
                target=server.run,
                daemon=True
            )
            server_thread.start()
            time.sleep(1)
            url = f"http://localhost:{port}"
            return url, self.shutdown_event
        
def run_server(df: pd.DataFrame, use_iframe: bool = False, collaborative: bool = False, test_mode: bool = False, log_level: str = "CRITICAL", strict_dtype: bool = True):
    server = ShareServer(df, collaborative_mode=collaborative, test_mode=test_mode, log_level=log_level, strict_dtype=strict_dtype)
    url, shutdown_event = server.serve(use_iframe=use_iframe)
    return url, shutdown_event, server

def run_ngrok(url, emails, shutdown_event):
    try:
        # Parse comma-separated emails if provided as a string
        if isinstance(emails, str):
            # Split by comma and strip whitespace from each email
            emails = [email.strip() for email in emails.split(',') if email.strip()]
        
        if not emails:
            print("No valid emails provided for sharing.")
            shutdown_event.set()
            return
        
        logger.info(f"Attempting to share with: {', '.join(emails)}")
        
        # Check if we're in a Jupyter notebook
        is_jupyter = False
        try:
            from IPython import get_ipython
            if get_ipython() is not None:
                is_jupyter = True
        except ImportError:
            pass
        
        if is_jupyter:
            # Handle asyncio in Jupyter environment
            import asyncio
            
            # Define the async function
            async def start_ngrok():
                listener = await ngrok.forward(
                    url, 
                    authtoken_from_env=True, 
                    oauth_provider="google", 
                    oauth_allow_emails=emails
                )
                print(f"Share this link: {listener.url()}")
                return listener
            
            # Use nest_asyncio to handle nested event loops in Jupyter
            try:
                import nest_asyncio
                nest_asyncio.apply()
            except ImportError:
                print("For best experience in Jupyter notebooks, install nest_asyncio: pip install nest_asyncio")
                
            # Run with asyncio
            listener = asyncio.get_event_loop().run_until_complete(start_ngrok())
            shutdown_event.wait()
        else:
            # Regular Python script - use normal approach
            listener = ngrok.forward(url, authtoken_from_env=True, oauth_provider="google", oauth_allow_emails=emails)
            print(f"Share this link: {listener.url()}")
            shutdown_event.wait()
            
    except Exception as e:
        if "ERR_NGROK_4018" in str(e):
            print("\nNgrok authentication token not found! Here's what you need to do:\n")
            print("1. Sign up for a free ngrok account at https://dashboard.ngrok.com/signup")
            print("2. Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken") 
            print("3. Create a file named '.env' in your project directory")
            print("4. Add this line to your .env file (replace with your actual token):")
            print("   NGROK_AUTHTOKEN=your_token_here\n")
            print("Once you've done this, try running the editor again!")
            shutdown_event.set()
        elif "ERR_NGROK_5511" in str(e):
            print("\nEmail authorization error. Please note:")
            print("1. You need a paid ngrok account to use OAuth restrictions")
            print("2. Make sure the emails you entered are exact and valid")
            print("3. Try without specifying emails or upgrade your ngrok account\n")
            print("Error details:", e)
            shutdown_event.set()
        elif "ERR_NGROK_324" in str(e):
            print("\nNgrok tunnel limit reached! Free accounts are limited to 3 active tunnels.")
            print("Options to fix this:")
            print("1. Close other ngrok tunnels you may have running")
            print("2. Upgrade to an ngrok paid plan")
            print("3. Try again later when some tunnels have expired\n")
            shutdown_event.set()
        else:
            logger.error(f"Error setting up ngrok: {e}")
            print(f"Error setting up ngrok: {e}")
            shutdown_event.set()

def start_editor(df, use_iframe: bool = False, collaborative: bool = False, share_with: List[str] = None, test_mode: bool = False, log_level: str = "CRITICAL", local: bool = False, strict_dtype: bool = True):
    
    load_dotenv()

    if not use_iframe:
        logger.info("Starting server with DataFrame:")
        logger.info(df)

    url, shutdown_event, server = run_server(
        df, 
        use_iframe=use_iframe, 
        collaborative=collaborative, 
        test_mode=test_mode, 
        log_level=log_level, 
        strict_dtype=strict_dtype
    )
    
    try:
        from google.colab import output
        # If that works we're in Colab
        if use_iframe:
            print("Editor opened in iframe below!")
        else:
            print("Above is the Google generated link, but unfortunately its not shareable to other users as of now!")
        shutdown_event.wait()
    except ImportError:
        # not in Colab
        if local:
            print(f"Local server started at {url}")
        
        if collaborative:
            if share_with:
                # In collaborative mode with emails to share with
                print(f"Collaborative mode enabled!")
                run_ngrok(url=url, emails=share_with, shutdown_event=shutdown_event)
            else:
                # Collaborative but no emails provided, ask for them
                email_input = input("Enter email(s) to share with (comma separated): ")
                run_ngrok(url=url, emails=email_input, shutdown_event=shutdown_event)
        else:
            # Standard mode
            email = input("Which gmail do you want to share this with? ")
            run_ngrok(url=url, emails=email, shutdown_event=shutdown_event)
    return server.df