import time
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

class ServerConfig(BaseModel):
    content: str
    title: str = "Shared Content"
    port: int = 8000
    host: str = "0.0.0.0"
    duration_hours: int = 24

class ShareServer:
    def __init__(self):
        self.app = FastAPI()
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            return self.content_html

    def serve(self, config: ServerConfig) -> str:
        """
        Start the server and return access URL
        
        Returns:
            str: url
        """
        self.content_html = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <title>{config.title}</title>
                <style>
                    body {{ 
                        font-family: Arial, sans-serif;
                        margin: 40px;
                        line-height: 1.6;
                    }}
                    table {{
                        border-collapse: collapse;
                        margin: 20px 0;
                    }}
                    th, td {{
                        border: 1px solid #ddd;
                        padding: 8px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #f5f5f5;
                    }}
                </style>
            </head>
            <body>
                <h1>{config.title}</h1>
                {config.content}
            </body>
        </html>
        """
        
        import threading
        server_thread = threading.Thread(
            target=uvicorn.run,
            args=(self.app,),
            kwargs={
                "host": config.host,
                "port": config.port,
                "log_level": "error"
            },
            daemon=True
        )
        server_thread.start()
        time.sleep(1)
        url = f"http://{config.host}:{config.port}"
        if config.host == "0.0.0.0":
            url = f"http://localhost:{config.port}"
            
        return url

def create_share_server(
    content: str,
    title: str = "Shared Content",
    port: int = 8000,
    host: str = "0.0.0.0",
    duration_hours: int = 24
) -> str:
    """
    Create a web server to share content
    
    Args:
        content: HTML content to share
        title: Page title
        port: Server port
        host: Server host
        duration_hours: How long the server should run
        
    Returns:
        str: url
    """
    config = ServerConfig(
        content=content,
        title=title,
        port=port,
        host=host,
        duration_hours=duration_hours
    )
    server = ShareServer()
    return server.serve(config)