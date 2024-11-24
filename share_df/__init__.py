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
                        <script src="https://cdnjs.cloudflare.com/ajax/libs/ag-grid/30.2.1/ag-grid-community.min.noStyle.js"></script>
                        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/ag-grid/30.2.1/styles/ag-grid.min.css">
                        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/ag-grid/30.2.1/styles/ag-theme-alpine.min.css">
                        <style>
                            .ag-theme-alpine {
                                height: 500px;
                                width: 100%;
                            }
                        </style>
                    </head>
                    <body>
                        <h2>DataFrame Editor</h2>
                        <div id="myGrid" class="ag-theme-alpine"></div>
                        <div style="margin-top: 20px;">
                            <button onclick="saveData()">Save Changes</button>
                            <button onclick="shutdownServer()">Shutdown Server</button>
                        </div>

                        <script>
                            let gridOptions;

                            async function shutdownServer() {
                                try {
                                    await fetch('/shutdown', {method: 'POST'});
                                } catch (e) {
                                    console.error('Error shutting down:', e);
                                }
                            }
                            
                            async function loadData() {
                                try {
                                    const response = await fetch('/data');
                                    const data = await response.json();
                                    console.log('Loaded data:', data);
                                    return data;
                                } catch (e) {
                                    console.error('Error loading data:', e);
                                    return [];
                                }
                            }
                            
                            async function saveData() {
                                try {
                                    const rowData = gridOptions.api.getRowData();
                                    await fetch('/update_data', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json',
                                        },
                                        body: JSON.stringify({data: rowData}),
                                    });
                                    alert('Data saved successfully!');
                                } catch (e) {
                                    console.error('Error saving data:', e);
                                    alert('Error saving data');
                                }
                            }
                            
                            async function initializeGrid() {
                                try {
                                    const data = await loadData();
                                    if (!data || data.length === 0) {
                                        console.error('No data received');
                                        return;
                                    }

                                    const columnDefs = Object.keys(data[0]).map(key => ({
                                        field: key,
                                        editable: true,
                                        sortable: true,
                                        filter: true
                                    }));
                                    
                                    gridOptions = {
                                        columnDefs: columnDefs,
                                        rowData: data,
                                        defaultColDef: {
                                            flex: 1,
                                            minWidth: 100,
                                            editable: true,
                                            sortable: true,
                                            filter: true
                                        },
                                    };
                                    
                                    const gridDiv = document.querySelector('#myGrid');
                                    new agGrid.Grid(gridDiv, gridOptions);
                                } catch (e) {
                                    console.error('Error initializing grid:', e);
                                }
                            }

                            document.addEventListener('DOMContentLoaded', () => {
                                // ensure AG Grid is fully loaded
                                setTimeout(initializeGrid, 100);
                            });
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