import time
import os
import ngrok
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import threading
import uvicorn

class ShareServer:
    def __init__(self):
        self.app = FastAPI()
        self.shutdown_event = threading.Event()
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            return """
                <!DOCTYPE html>
                <html>
                    <head>
                        <title>Control Panel</title>
                        <script>
                            async function shutdownServer() {
                                await fetch('/shutdown', {method: 'POST'});
                            }
                        </script>
                    </head>
                    <body>
                        <h2>Control Panel</h2>
                        <button onclick="shutdownServer()">Shutdown Server</button>
                    </body>
                </html>
            """
            
        @self.app.post("/shutdown")
        async def shutdown():
            self.shutdown_event.set()
            return {"status": "shutting down"}

    def serve(self, host="0.0.0.0", port=8000):
        server_thread = threading.Thread(
            target=uvicorn.run,
            args=(self.app,),
            kwargs={
                "host": host,
                "port": port,
                "log_level": "error"
            },
            daemon=True
        )
        server_thread.start()
        time.sleep(1)
        url = f"http://localhost:{port}"
        return url, self.shutdown_event

def run_server():
    server = ShareServer()
    return server.serve()

def run_ngrok(url, email, shutdown_event):
    listener = ngrok.forward(url, authtoken_from_env=True, oauth_provider="google", oauth_allow_emails=email)
    print(f"Ingress established at: {listener.url()}")
    shutdown_event.wait()

def main():
    url, shutdown_event = run_server()
    email = input("Which gmail do you want to share this with? ")
    run_ngrok(url=url, email=email, shutdown_event=shutdown_event)

if __name__=="__main__":
    main()