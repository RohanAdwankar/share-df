import time
import os
import ngrok
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import threading
import uvicorn
import pandas as pd
from pydantic import BaseModel
from typing import List, Dict, Any

class DataUpdate(BaseModel):
    data: List[Dict[Any, Any]]

class ShareServer:
    def __init__(self, df: pd.DataFrame):
        self.app = FastAPI()
        self.shutdown_event = threading.Event()
        self.df = df
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            return """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>DataFrame Editor</title>
                    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tabulator/5.4.4/css/tabulator.min.css">
                    <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/tabulator/5.4.4/js/tabulator.min.js"></script>
                    <style>
                        * {
                            margin: 0;
                            padding: 0;
                            box-sizing: border-box;
                        }

                        body {
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                            background: #f1f5f9;
                            height: 100vh;
                            display: flex;
                            flex-direction: column;
                        }

                        .header {
                            background: #3b82f6;
                            padding: 1rem 2rem;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                        }

                        .title {
                            color: white;
                            font-size: 1.5rem;
                            font-weight: 600;
                        }

                        .button-container {
                            display: flex;
                            gap: 1rem;
                        }

                        .button {
                            padding: 0.5rem 1rem;
                            border: none;
                            border-radius: 6px;
                            font-weight: 500;
                            cursor: pointer;
                            transition: all 0.2s ease;
                            display: flex;
                            align-items: center;
                            gap: 0.5rem;
                            color: white;
                            font-size: 0.9rem;
                        }

                        .save-button {
                            background: #22c55e;
                        }

                        .save-button:hover {
                            background: #16a34a;
                        }

                        .shutdown-button {
                            background: #ef4444;
                        }

                        .shutdown-button:hover {
                            background: #dc2626;
                        }

                        .grid-container {
                            flex: 1;
                            padding: 1rem;
                            height: calc(100vh - 64px);
                            background: white;
                            margin: 1rem;
                            border-radius: 8px;
                            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                        }

                        /* Tabulator Customization */
                        .tabulator {
                            border: 1px solid #e2e8f0;
                            border-radius: 8px;
                            overflow: hidden;
                            font-family: inherit;
                        }

                        .tabulator .tabulator-header {
                            background-color: #f8fafc;
                            border-bottom: 2px solid #e2e8f0;
                        }

                        .tabulator .tabulator-header .tabulator-col {
                            background-color: #f8fafc;
                            border-right: 1px solid #e2e8f0;
                            padding: 8px;
                        }

                        .tabulator .tabulator-header .tabulator-col-content {
                            font-weight: 600;
                            color: #1e293b;
                        }

                        .tabulator .tabulator-row {
                            border-bottom: 1px solid #e2e8f0;
                        }

                        .tabulator .tabulator-row .tabulator-cell {
                            padding: 8px;
                            border-right: 1px solid #e2e8f0;
                        }

                        .tabulator .tabulator-row.tabulator-row-even {
                            background-color: #f8fafc;
                        }

                        .tabulator-row.tabulator-selected {
                            background-color: #e2e8f0 !important;
                        }

                        .tabulator-editing {
                            background-color: #fff !important;
                            border: 2px solid #3b82f6 !important;
                        }

                        .toast {
                            position: fixed;
                            top: 1rem;
                            right: 1rem;
                            padding: 0.75rem 1.5rem;
                            border-radius: 6px;
                            color: white;
                            font-weight: 500;
                            animation: slideInRight 0.3s ease-out, fadeOut 0.3s ease-out 2s forwards;
                            z-index: 1000;
                        }

                        .toast.success {
                            background: #22c55e;
                        }

                        .toast.error {
                            background: #ef4444;
                        }

                        @keyframes slideInRight {
                            from { transform: translateX(100%); opacity: 0; }
                            to { transform: translateX(0); opacity: 1; }
                        }

                        @keyframes fadeOut {
                            from { opacity: 1; }
                            to { opacity: 0; }
                        }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1 class="title">DataFrame Editor</h1>
                        <div class="button-container">
                            <button onclick="saveData()" class="button save-button">
                                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                                </svg>
                                Save Changes
                            </button>
                            <button onclick="shutdownServer()" class="button shutdown-button">
                                <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                </svg>
                                Shutdown Server
                            </button>
                        </div>
                    </div>
                    
                    <div class="grid-container">
                        <div id="data-table"></div>
                    </div>

                    <script>
                        let table;

                        function showToast(message, type = 'success') {
                            const toast = document.createElement('div');
                            toast.className = `toast ${type}`;
                            toast.textContent = message;
                            document.body.appendChild(toast);
                            
                            setTimeout(() => {
                                toast.remove();
                            }, 2300);
                        }

                        async function shutdownServer() {
                            if (confirm('Are you sure you want to shutdown the server?')) {
                                try {
                                    await fetch('/shutdown', {method: 'POST'});
                                    showToast('Server shutting down...', 'success');
                                } catch (e) {
                                    console.error('Error shutting down:', e);
                                    showToast('Error shutting down server', 'error');
                                }
                            }
                        }
                        
                        async function loadData() {
                            try {
                                const response = await fetch('/data');
                                const data = await response.json();
                                return data;
                            } catch (e) {
                                console.error('Error loading data:', e);
                                showToast('Error loading data', 'error');
                                return [];
                            }
                        }
                        
                        async function saveData() {
                            try {
                                const data = table.getData();
                                await fetch('/update_data', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({data: data}),
                                });
                                showToast('Changes saved successfully!');
                            } catch (e) {
                                console.error('Error saving data:', e);
                                showToast('Error saving data', 'error');
                            }
                        }
                        
                        async function initializeTable() {
                            try {
                                const data = await loadData();
                                if (!data || data.length === 0) {
                                    console.error('No data received');
                                    showToast('No data available', 'error');
                                    return;
                                }

                                const columns = Object.keys(data[0]).map(key => ({
                                    title: key.charAt(0).toUpperCase() + key.slice(1),
                                    field: key,
                                    editor: "input",
                                    headerSort: true,
                                    resizable: true
                                }));

                                table = new Tabulator("#data-table", {
                                    data: data,
                                    columns: columns,
                                    layout: "fitDataFill",
                                    height: "100%",
                                    movableColumns: true,
                                    selectable: true,
                                    history: true,
                                    clipboard: true,
                                    keybindings: {
                                        "copyToClipboard": "ctrl+67",
                                        "pasteFromClipboard": "ctrl+86",
                                        "undo": "ctrl+90",
                                        "redo": "ctrl+89"
                                    }
                                });
                            } catch (e) {
                                console.error('Error initializing table:', e);
                                showToast('Error initializing table', 'error');
                            }
                        }

                        document.addEventListener('DOMContentLoaded', initializeTable);
                    </script>
                </body>
                </html>
            """
            
        @self.app.get("/data")
        async def get_data():
            data = self.df.to_dict(orient='records')
            print("Sending data:", data)
            return JSONResponse(content=data)
            
        @self.app.post("/update_data")
        async def update_data(data_update: DataUpdate):
            self.df = pd.DataFrame(data_update.data)
            print("Updated DataFrame:", self.df)
            return {"status": "success"}
            
        @self.app.post("/shutdown")
        async def shutdown():
            self.shutdown_event.set()
            return {"status": "shutting down"}

    def serve(self, host="0.0.0.0", port=8000):
        server_config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info"
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

def run_server(df: pd.DataFrame):
    server = ShareServer(df)
    return server.serve()

def run_ngrok(url, email, shutdown_event):
    try:
        listener = ngrok.forward(url, authtoken_from_env=True, oauth_provider="google", oauth_allow_emails=[email])
        print(f"Ingress established at: {listener.url()}")
        shutdown_event.wait()
    except Exception as e:
        print(f"Error setting up ngrok: {e}")

def main():
    df = pd.DataFrame({
        'Name': ['John', 'Alice', 'Bob', 'Carol'],
        'Age': [25, 30, 35, 28],
        'City': ['New York', 'London', 'Paris', 'Tokyo'],
        'Salary': [50000, 60000, 75000, 65000]
    })
    
    print("Starting server with DataFrame:")
    print(df)
    
    url, shutdown_event = run_server(df)
    print(f"Server started at {url}")
    
    email = input("Which gmail do you want to share this with? ")
    run_ngrok(url=url, email=email, shutdown_event=shutdown_event)

if __name__=="__main__":
    main()