import secrets
import string
import time
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import hmac

class ServerConfig(BaseModel):
    content: str
    title: str = "Shared Content"
    port: int = 8000
    host: str = "0.0.0.0"
    duration_hours: int = 24

class ShareServer:
    def __init__(self):
        self.app = FastAPI()
        self.security = HTTPBasic()
        self.credentials: Dict[str, str] = {}
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root(credentials: HTTPBasicCredentials = Depends(self.security)):
            if not self._verify_credentials(credentials):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Basic"},
                )
            return self.content_html

    def _generate_credentials(self) -> tuple[str, str]:
        """Generate random username and password"""
        username = ''.join(secrets.choice(string.ascii_letters) for _ in range(8))
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        return username, password

    def _verify_credentials(self, credentials: HTTPBasicCredentials) -> bool:
        """Verify provided credentials using constant time comparison"""
        stored_password = self.credentials.get(credentials.username)
        if not stored_password:
            return False
        return hmac.compare_digest(stored_password, credentials.password)

    def serve(self, config: ServerConfig) -> tuple[str, str, str]:
        """
        Start the server and return access details
        
        Returns:
            tuple: (url, username, password)
        """
        username, password = self._generate_credentials()
        self.credentials[username] = password
        
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
            
        return url, username, password

def create_share_server(
    content: str,
    title: str = "Shared Content",
    port: int = 8000,
    host: str = "0.0.0.0",
    duration_hours: int = 24
) -> tuple[str, str, str]:
    """
    Create a secure web server to share content
    
    Args:
        content: HTML content to share
        title: Page title
        port: Server port
        host: Server host
        duration_hours: How long the server should run
        
    Returns:
        tuple: (url, username, password)
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