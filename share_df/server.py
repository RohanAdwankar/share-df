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
from dotenv import load_dotenv

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
                            overflow: hidden;
                        }

                        .header {
                            background: #3b82f6;
                            padding: 0.75rem 1.5rem;
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
                            padding: 1rem;
                            flex: 1;
                            min-height: 0;
                            display: flex;
                            flex-direction: column;
                        }

                        #data-table {
                            flex: 1;
                            background: white;
                            border-radius: 8px;
                            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                            overflow: hidden;
                        }

                        .tabulator {
                            border: 1px solid #e2e8f0;
                            border-radius: 8px;
                            max-height: 100%;
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
                            padding: 0;
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
                            padding: 0 !important;
                        }

                        .tabulator-editing input {
                            border: 2px solid #3b82f6 !important;
                            padding: 6px !important;
                            width: 100% !important;
                            height: 100% !important;
                            box-sizing: border-box !important;
                        }

                        .tabulator-row-handle {
                            display: inline-block;
                            vertical-align: middle;
                            white-space: nowrap;
                            cursor: move;
                            width: 30px;
                            max-width: 30px;
                            height: 100%;
                            text-align: center;
                            background: #f8fafc;
                            border-right: 1px solid #e2e8f0;
                        }

                        .tabulator-row-handle::before {
                            content: "≡";
                            font-size: 20px;
                            color: #64748b;
                            line-height: 40px;
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

                        .button-container {
                            display: flex;
                            gap: 0.5rem;
                        }

                        .button-group {
                            display: flex;
                            gap: 0.5rem;
                            padding-right: 1rem;
                            border-right: 1px solid rgba(255, 255, 255, 0.2);
                            margin-right: 1rem;
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

                        .add-button {
                            background: #6366f1;
                        }

                        .add-button:hover {
                            background: #4f46e5;
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
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1 class="title">DataFrame Editor</h1>
                        <div class="button-container">
                            <div class="button-group">
                                <button onclick="addNewColumn()" class="button add-button">
                                    <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v12m6-6H6"></path>
                                    </svg>
                                    Add Column
                                </button>
                                <button onclick="addNewRow()" class="button add-button">
                                    <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v12m6-6H6"></path>
                                    </svg>
                                    Add Row
                                </button>
                            </div>
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
                        let columnCount = 0;

                        function showToast(message, type = 'success') {
                            const toast = document.createElement('div');
                            toast.className = `toast ${type}`;
                            toast.textContent = message;
                            document.body.appendChild(toast);
                            setTimeout(() => toast.remove(), 2300);
                        }

                        function addNewColumn() {
                            columnCount++;
                            const newColumnName = `New Column ${columnCount}`;
                            
                            table.addColumn({
                                title: newColumnName,
                                field: newColumnName,
                                editor: true,
                                headerClick: function(e, column) {
                                    editColumnHeader(e, column);
                                }
                            }, false);  // false means add to end of table
                        }

                        function addNewRow() {
                            const columns = table.getColumns();
                            const newRow = {};
                            columns.forEach(column => {
                                newRow[column.getField()] = '';
                            });
                            table.addRow(newRow);
                        }

                        function editColumnHeader(e, column) {
                            // Prevent header click from triggering sort
                            e.stopPropagation();

                            const currentTitle = column.getDefinition().title;
                            const oldField = column.getField();
                            
                            const input = document.createElement("input");
                            input.value = currentTitle;
                            input.style.width = "100%";
                            input.style.boxSizing = "border-box";
                            input.style.padding = "5px";
                            input.style.border = "2px solid #3b82f6";
                            input.style.borderRadius = "4px";
                            
                            const headerElement = e.target.closest(".tabulator-col");
                            const titleElement = headerElement.querySelector(".tabulator-col-title");
                            titleElement.innerHTML = "";
                            titleElement.appendChild(input);
                            input.focus();
                            
                            const finishEdit = function(newValue) {
                                if (newValue && newValue !== oldField) {
                                    const allData = table.getData();
                                    const columnDefinitions = table.getColumnDefinitions();
                                    
                                    const newColumnDefinitions = columnDefinitions.map(def => {
                                        if (def.field === oldField) {
                                            return {
                                                ...def,
                                                title: newValue,
                                                field: newValue
                                            };
                                        }
                                        return def;
                                    });

                                    // Update data with new field name
                                    const updatedData = allData.map(row => {
                                        const newRow = {...row};
                                        newRow[newValue] = row[oldField];
                                        delete newRow[oldField];
                                        return newRow;
                                    });

                                    // Rebuild table with new columns and data
                                    table.setColumns(newColumnDefinitions);
                                    table.setData(updatedData);
                                } else {
                                    // If no change, just restore the original title
                                    titleElement.innerHTML = currentTitle;
                                }
                            };
                            
                            input.addEventListener("blur", function() {
                                finishEdit(this.value);
                            });
                            
                            input.addEventListener("keydown", function(e) {
                                if (e.key === "Enter") {
                                    finishEdit(this.value);
                                    this.blur();
                                }
                                if (e.key === "Escape") {
                                    titleElement.innerHTML = currentTitle;
                                    this.blur();
                                }
                            });
                        }

                        async function initializeTable() {
                            try {
                                const data = await loadData();
                                if (!data || data.length === 0) {
                                    console.error('No data received');
                                    showToast('No data available', 'error');
                                    return;
                                }

                                const columns = [
                                    {
                                        formatter: "handle",
                                        headerSort: false,
                                        frozen: true,
                                        width: 30,
                                        minWidth: 30,
                                        cssClass: "tabulator-row-handle",
                                    },
                                    ...Object.keys(data[0]).map(key => ({
                                        title: key,
                                        field: key,
                                        editor: true,
                                        headerClick: function(e, column) {
                                            editColumnHeader(e, column);
                                        }
                                    }))
                                ];

                                table = new Tabulator("#data-table", {
                                    data: data,
                                    columns: columns,
                                    layout: "fitColumns",
                                    movableColumns: true,
                                    movableRows: true,
                                    history: true,
                                    clipboard: true,
                                    height: "100%",
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

                        async function shutdownServer() {
                            if (confirm('Are you sure you want to shutdown the server?')) {
                                try {
                                    saveData();
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
                                    body: JSON.stringify({data}),
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
                                    title: key,
                                    field: key,
                                    editor: true,
                                    headerClick: function(e, column) {
                                        editColumnHeader(e, column);
                                    }
                                }));

                                table = new Tabulator("#data-table", {
                                    data: data,
                                    columns: columns,
                                    layout: "fitColumns",
                                    movableColumns: true,
                                    history: true,
                                    clipboard: true,
                                    height: "100%",
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
            print("Updated DataFrame:\n", self.df)
            return {"status": "success"}
            
        @self.app.post("/shutdown")
        async def shutdown():
            self.shutdown_event.set()
            return {"status": "shutting down"}

    def serve(self, host="0.0.0.0", port=8000):
        try:
            from google.colab import output
            # If that works we're in Colab
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

def run_server(df: pd.DataFrame):
    server = ShareServer(df)
    url, shutdown_event = server.serve()
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

def start_editor(df):
    load_dotenv()
    print("Starting server with DataFrame:")
    print(df)
    url, shutdown_event, server = run_server(df)
    try:
        from google.colab import output
        # If that works we're in Colab
        print("Above is the Google generated link, but unfortunately its not shareable to other users as of now!")
        shutdown_event.wait()
    except ImportError:
        #not in Colab
        print(f"Local server started at {url}")
        email = input("Which gmail do you want to share this with? ")
        run_ngrok(url=url, email=email, shutdown_event=shutdown_event)
    return server.df