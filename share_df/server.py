import time
import threading
import uvicorn
import pandas as pd
import polars as pl
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Union
from .models import DataUpdate
import os
import ngrok
from dotenv import load_dotenv

class ShareServer:
    def __init__(self, df: Union[pd.DataFrame, pl.DataFrame]):
        self.app = FastAPI()
        self.shutdown_event = threading.Event()
        
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
                request,
                "editor.html",
                {"request": request}
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
        
def run_server(df: pd.DataFrame, use_iframe: bool = False):
    server = ShareServer(df)
    url, shutdown_event = server.serve(use_iframe=use_iframe)
    return url, shutdown_event, server

def run_ngrok(url, email, shutdown_event):
    try:
        listener = ngrok.forward(url, authtoken_from_env=True, oauth_provider="google", oauth_allow_emails=[email])
        print(f"Ingress established at: {listener.url()}")
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
        else:
            print(f"Error setting up ngrok: {e}")
            shutdown_event.set()

def start_editor(df, use_iframe: bool = False):
    load_dotenv()
    if not use_iframe:
        print("Starting server with DataFrame:")
        print(df)
    url, shutdown_event, server = run_server(df, use_iframe=use_iframe)
    try:
        from google.colab import output
        # If that works we're in Colab
        if use_iframe:
            print("Editor opened in iframe below!")
        else:
            print("Above is the Google generated link, but unfortunately its not shareable to other users as of now!")        
        shutdown_event.wait()
    except ImportError:
        #not in Colab
        print(f"Local server started at {url}")
        email = input("Which gmail do you want to share this with? ")
        run_ngrok(url=url, email=email, shutdown_event=shutdown_event)
    return server.df