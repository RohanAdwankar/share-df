import time
import threading
import uvicorn
import pandas as pd
import polars as pl
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Union, Dict, List
from .models import DataUpdate, CollaboratorInfo
import os
import ngrok
from dotenv import load_dotenv
import json
import uuid

class ShareServer:
    def __init__(self, df: Union[pd.DataFrame, pl.DataFrame], collaborative_mode: bool = True):
        self.app = FastAPI()
        self.shutdown_event = threading.Event()
        self.collaborative_mode = collaborative_mode
        self.active_connections: Dict[str, WebSocket] = {}
        self.collaborators: Dict[str, CollaboratorInfo] = {}
        self.cell_editors: Dict[str, str] = {}  # Maps cell ID to user ID of current editor
        
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
    
    def setup_routes(self):
        @self.app.get("/")
        async def root(request: Request):
            return self.templates.TemplateResponse(
                "editor.html",
                {"request": request, "collaborative": self.collaborative_mode}
            )
            
        @self.app.get("/data")
        async def get_data():
            data = self.df.to_dict(orient='records')
            print("Sending data:", data)
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
                
            print("Updated DataFrame:\n", self.df)
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
                
            print("Updated DataFrame from collaborative save:\n", self.df)
            
            # Broadcast data update to all users
            if self.collaborative_mode:
                await self.broadcast({
                    "type": "data_sync",
                    "message": "Data has been updated by another user"
                })
            
            return {"status": "success", "message": "Data saved without shutting down"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            user_id = str(uuid.uuid4())
            user_name = f"User {user_id[:6]}"
            self.active_connections[user_id] = websocket
            
            try:
                print(f"New WebSocket connection: {user_id}")
                
                # Send current state to the new user
                await websocket.send_json({
                    "type": "init",
                    "userId": user_id,
                    "collaborators": [collab.dict() for collab in self.collaborators.values()]
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
                    
                    print(f"Received message from {user_id}: {message_type}")
                    
                    # Add debug ping handler
                    if message_type == "debug_ping":
                        timestamp = message.get("timestamp", 0)
                        now = int(time.time() * 1000)
                        latency = now - timestamp
                        
                        print(f"Debug ping from {user_id}: latency {latency}ms")
                        
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
                        # User edited a cell
                        row_id = message.get("rowId")
                        column = message.get("column")
                        value = message.get("value")
                        
                        print(f"Cell edit from {user_id}: [{row_id}, {column}] = {value}")
                        
                        # Update the dataframe
                        if row_id is not None and column is not None:
                            try:
                                row_index = int(row_id) if isinstance(row_id, str) and row_id.isdigit() else row_id
                                if isinstance(row_index, int) and 0 <= row_index < len(self.df):
                                    # Explicitly convert the value to match the column type if possible
                                    try:
                                        existing_val = self.df.at[row_index, column]
                                        if isinstance(existing_val, (int, float)) and not isinstance(value, bool):
                                            if isinstance(existing_val, int):
                                                value = int(float(value)) if value else 0
                                            else:
                                                value = float(value) if value else 0.0
                                    except (ValueError, TypeError):
                                        # If conversion fails, use the value as is
                                        pass
                                        
                                    self.df.at[row_index, column] = value
                                    print(f"Updated DataFrame at [{row_index}, {column}] = {value}")
                            except Exception as e:
                                print(f"Error updating DataFrame: {e}")
                        
                        # Broadcast edit to EVERYONE (including the sender for confirmation)
                        await self.broadcast({
                            "type": "cell_edit",
                            "rowId": row_id,
                            "column": column,
                            "value": value,
                            "userId": user_id
                        })
                        
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
                        operation_id = message.get("operationId", "") # Pass through the operation ID
                        
                        print(f"User {user_id} added column: {column_name}")
                        
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
                        operation_id = message.get("operationId", "") # Pass through the operation ID
                        
                        print(f"User {user_id} added row at position: {row_id}")
                        
                        # Broadcast to everyone
                        await self.broadcast({
                            "type": "add_row",
                            "rowId": row_id,
                            "userId": user_id,
                            "operationId": operation_id
                        })
                    
                    elif message_type == "user_finished":
                        # User is leaving but server continues for others
                        print(f"User {user_id} is finishing their session")
                        
                        # Let everyone know this user is leaving
                        await self.broadcast({
                            "type": "user_finished",
                            "userId": user_id,
                            "name": self.collaborators[user_id].name if user_id in self.collaborators else user_name
                        })
            
            except WebSocketDisconnect:
                print(f"WebSocket disconnected: {user_id}")
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
                print(f"WebSocket error for {user_id}: {e}")
                if user_id in self.active_connections:
                    del self.active_connections[user_id]
                if user_id in self.collaborators:
                    del self.collaborators[user_id]
    
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
                print(f"Skipping duplicate message: {message_key}")
                return
                
        # Update message timestamp
        self.recent_messages[message_key] = current_time
        
        # Clean up old messages (older than 5 seconds)
        self.recent_messages = {k: v for k, v in self.recent_messages.items() 
                               if current_time - v < 5.0}
        
        if msg_type == 'cell_edit':
            extra_info = f" - Cell [{message.get('rowId')}, {message.get('column')}] = {message.get('value')}"
        
        print(f"Broadcasting '{msg_type}'{extra_info} to {client_count} client(s)" + 
              (f" (excluding {exclude})" if exclude else ""))
        
        sent_count = 0
        for client_id, connection in self.active_connections.items():
            if exclude is None or client_id != exclude:
                try:
                    await connection.send_json(message)
                    sent_count += 1
                except Exception as e:
                    print(f"Error broadcasting to {client_id}: {e}")
        
        print(f"Message sent to {sent_count}/{client_count} client(s)")

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
            time.sleep(1)
            url = f"http://localhost:{port}"
            return url, self.shutdown_event
        
def run_server(df: pd.DataFrame, use_iframe: bool = False, collaborative: bool = False):
    server = ShareServer(df, collaborative_mode=collaborative)
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
        
        print(f"Attempting to share with: {', '.join(emails)}")
        
        listener = ngrok.forward(url, authtoken_from_env=True, oauth_provider="google", oauth_allow_emails=emails)
        print(f"Ingress established at: {listener.url()}")
        print(f"Share this URL with these email addresses: {', '.join(emails)}")
        print("Note: Recipients must log in with the exact email address you specified.")
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
        else:
            print(f"Error setting up ngrok: {e}")
            shutdown_event.set()

def start_editor(df, use_iframe: bool = False, collaborative: bool = False, share_with: List[str] = None):
    load_dotenv()
    if not use_iframe:
        print("Starting server with DataFrame:")
        print(df)
    url, shutdown_event, server = run_server(df, use_iframe=use_iframe, collaborative=collaborative)
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