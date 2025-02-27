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
    def __init__(self, df: Union[pd.DataFrame, pl.DataFrame], collaborative_mode: bool = False):
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
    
    def setup_routes(self):
        @self.app.get("/")
        async def root(request: Request):
            return self.templates.TemplateResponse(
                "editor-alpine.html",  # Using the Alpine.js template
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
                        
                    elif message_type == "cursor_move":
                        # User moved their cursor
                        if user_id in self.collaborators:
                            self.collaborators[user_id].cursor = message.get("cursor", {"row": -1, "col": -1})
                            
                            # Broadcast cursor position to everyone else
                            await self.broadcast({
                                "type": "cursor_move",
                                "userId": user_id,
                                "cursor": self.collaborators[user_id].cursor
                            }, exclude=user_id)
            
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