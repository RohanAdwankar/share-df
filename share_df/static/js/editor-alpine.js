
function editorApp(isCollaborative) {
    return {
        // State variables
        table: null,
        isCollaborative,
        loading: true,
        loadingText: 'Loading data...',
        tableData: [],
        columnCount: 0,
        socket: null,
        userId: null,
        collaborators: {},
        userName: `User ${Math.floor(Math.random() * 1000)}`,
        userColor: null,
        isConnected: false,
        
        // Initialize the application
        async init() {
            this.userColor = this.getRandomColor();
            await this.loadData();
            this.initializeTable();
            
            if (this.isCollaborative) {
                this.setupWebSocket();
            }
        },
        
        // Load data from the server
        async loadData() {
            try {
                this.loading = true;
                const response = await fetch('/data');
                const data = await response.json();
                if (!data || data.length === 0) {
                    this.showToast('No data available', 'error');
                    return [];
                }
                this.loadingText = `Preparing ${data.length.toLocaleString()} rows...`;
                this.tableData = data;
                return data;
            } catch (e) {
                console.error('Error loading data:', e);
                this.showToast('Error loading data', 'error');
                return [];
            } finally {
                this.loading = false;
            }
        },
        
        // Initialize the Tabulator table
        initializeTable() {
            if (this.tableData.length === 0) {
                console.error('No data available to initialize table');
                return;
            }
            
            const columns = Object.keys(this.tableData[0]).map(key => ({
                title: key,
                field: key,
                editor: true,
                headerClick: (e, column) => this.editColumnHeader(e, column)
            }));
            
            this.table = new Tabulator("#data-table", {
                data: this.tableData,
                columns: columns,
                layout: "fitColumns",
                movableColumns: true,
                history: true,
                clipboard: true,
                height: "100%",
                reactiveData: true,
                keybindings: {
                    "copyToClipboard": "ctrl+67",
                    "pasteFromClipboard": "ctrl+86",
                    "undo": "ctrl+90",
                    "redo": "ctrl+89"
                }
            });
            
            // Set up cell events for collaborative mode
            if (this.isCollaborative) {
                this.setupCellEvents();
            }
        },
        
        // Save data back to the server
        async saveData() {
            try {
                if (!this.table) return;
                const data = this.table.getData();
                await fetch('/update_data', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({data}),
                });
                this.showToast('Changes saved successfully!');
            } catch (e) {
                console.error('Error saving data:', e);
                this.showToast('Error saving data', 'error');
            }
        },
        
        // Add a new column to the table
        addNewColumn() {
            this.columnCount++;
            const newColumnName = `New Column ${this.columnCount}`;
            
            this.table.addColumn({
                title: newColumnName,
                field: newColumnName,
                editor: true,
                headerClick: (e, column) => this.editColumnHeader(e, column)
            }, false);
        },
        
        // Add a new row to the table
        addNewRow() {
            const columns = this.table.getColumns();
            const newRow = {};
            columns.forEach(column => {
                newRow[column.getField()] = '';
            });
            this.table.addRow(newRow);
        },
        
        // Edit column header
        editColumnHeader(e, column) {
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
            
            const finishEdit = (newValue) => {
                if (newValue && newValue !== oldField) {
                    const allData = this.table.getData();
                    const columnDefinitions = this.table.getColumnDefinitions();
                    
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

                    const updatedData = allData.map(row => {
                        const newRow = {...row};
                        newRow[newValue] = row[oldField];
                        delete newRow[oldField];
                        return newRow;
                    });

                    this.table.setColumns(newColumnDefinitions);
                    this.table.setData(updatedData);
                } else {
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
        },
        
        // Set up WebSocket connection for real-time collaboration
        setupWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            const wsUrl = `${protocol}${window.location.host}/ws`;
            
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = (e) => {
                console.log("WebSocket connection established");
                this.isConnected = true;
                
                // Ask for user name when first connecting
                const name = prompt("Enter your name for collaboration:", this.userName) || this.userName;
                this.userName = name;
                
                // Send user info to server
                this.socket.send(JSON.stringify({
                    type: "update_user",
                    name: this.userName,
                    color: this.userColor
                }));
            };
            
            this.socket.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.socket.onclose = (event) => {
                console.log("WebSocket connection closed");
                this.isConnected = false;
                
                if (event.wasClean) {
                    this.showToast(`Connection closed: ${event.reason}`, 'error');
                } else {
                    // Connection died
                    this.showToast("Connection lost. Please refresh the page.", 'error');
                }
            };
            
            this.socket.onerror = (error) => {
                console.error("WebSocket error:", error);
                this.showToast("WebSocket error occurred", 'error');
            };
            
            // Track mouse movement for cursor sharing
            this.trackMouseMovement();
        },
        
        // Handle incoming WebSocket messages
        handleWebSocketMessage(message) {
            console.log("Received message:", message);
            
            switch (message.type) {
                case "init":
                    // Initialize with server-provided data
                    this.userId = message.userId;
                    
                    // Add existing collaborators
                    message.collaborators.forEach(user => {
                        if (user.id !== this.userId) {
                            this.collaborators[user.id] = user;
                        }
                    });
                    break;
                    
                case "user_joined":
                    this.showToast(`${message.name || "A new user"} joined the session`, 'success');
                    break;
                    
                case "user_update":
                    // Update or add collaborator
                    if (message.user && message.user.id !== this.userId) {
                        this.collaborators[message.user.id] = message.user;
                        
                        // Show toast for first update from a user
                        if (!document.querySelector(`.collaborator-badge[data-user-id="${message.user.id}"]`)) {
                            this.showToast(`${message.user.name} joined the session`, 'success');
                        }
                    }
                    break;
                    
                case "user_left":
                    // Remove collaborator
                    if (message.userId && this.collaborators[message.userId]) {
                        const userName = this.collaborators[message.userId].name;
                        delete this.collaborators[message.userId];
                        
                        // Remove any cursors for this user
                        document.querySelectorAll(`.user-cursor[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                        
                        this.showToast(`${userName} left the session`, 'error');
                    }
                    break;
                    
                case "cell_focus":
                    // Another user is focusing on a cell
                    if (message.userId !== this.userId) {
                        const cellId = message.cellId;
                        const [rowId, colField] = cellId.split("-");
                        
                        const cell = this.table.getCell(rowId, colField);
                        if (cell && cell.getElement()) {
                            const userName = this.collaborators[message.userId]?.name || "User";
                            const userColor = this.collaborators[message.userId]?.color || "#3b82f6";
                            
                            // Mark the cell as being edited
                            cell.getElement().classList.add("cell-being-edited");
                            cell.getElement().style.boxShadow = `0 0 0 2px ${userColor} inset`;
                            
                            // Add editor name
                            const nameTag = document.createElement("div");
                            nameTag.className = "editor-name";
                            nameTag.textContent = userName;
                            nameTag.style.backgroundColor = userColor;
                            nameTag.style.color = "#ffffff";
                            cell.getElement().appendChild(nameTag);
                        }
                    }
                    break;
                    
                case "cell_blur":
                    // User stopped editing a cell
                    if (message.userId !== this.userId) {
                        const cellId = message.cellId;
                        const [rowId, colField] = cellId.split("-");
                        
                        const cell = this.table.getCell(rowId, colField);
                        if (cell && cell.getElement()) {
                            cell.getElement().classList.remove("cell-being-edited");
                            cell.getElement().style.boxShadow = "";
                            
                            // Remove editor name
                            const nameTag = cell.getElement().querySelector(".editor-name");
                            if (nameTag) nameTag.remove();
                        }
                    }
                    break;
                    
                case "cell_edit":
                    // Another user edited a cell
                    if (message.userId !== this.userId) {
                        const rowId = message.rowId;
                        const column = message.column;
                        const value = message.value;
                        
                        console.log(`Received cell edit: [${rowId}, ${column}] = ${value}`);
                        
                        try {
                            // Important: Force table update through direct cell setValue
                            const cell = this.table.getCell(rowId, column);
                            if (cell) {
                                cell.setValue(value);
                                console.log(`Updated cell: [${rowId}, ${column}] to ${value}`);
                            } else {
                                console.warn(`Could not find cell: [${rowId}, ${column}]`);
                                
                                // Fallback: manually update the data and redraw
                                const rowData = this.table.getRow(rowId)?.getData();
                                if (rowData) {
                                    rowData[column] = value;
                                    this.table.updateData([rowData]);
                                    console.log(`Updated row data for row ${rowId}`);
                                }
                            }
                        } catch (e) {
                            console.error("Error updating cell:", e);
                        }
                    }
                    break;
                    
                case "cursor_move":
                    // Another user moved their cursor
                    if (message.userId !== this.userId && message.cursor) {
                        this.updateCursor(message.userId, message.cursor);
                    }
                    break;
            }
        },
        
        // Set up cell events for collaborative editing
        setupCellEvents() {
            // Listen for cell edit start events
            this.table.on("cellEditing", (cell) => {
                const row = cell.getRow().getData().id || cell.getRow().getPosition();
                const column = cell.getColumn().getField();
                this.sendCellFocus(row, column);
            });
            
            // Listen for cell edit events
            this.table.on("cellEdited", (cell) => {
                const row = cell.getRow().getData().id || cell.getRow().getPosition();
                const column = cell.getColumn().getField();
                const value = cell.getValue();
                
                console.log(`Sending edit for cell [${row}, ${column}] = ${value}`);
                
                // Save value locally first
                this.tableData = this.table.getData();
                
                // Send edit to server immediately
                this.sendCellEdit(row, column, value);
            });
            
            // Listen for cell blur events
            this.table.on("cellEditCancelled", (cell) => {
                const row = cell.getRow().getData().id || cell.getRow().getPosition();
                const column = cell.getColumn().getField();
                this.sendCellBlur(row, column);
            });
        },
        
        // Send cell focus event via WebSocket
        sendCellFocus(row, column) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            const cellId = `${row}-${column}`;
            this.socket.send(JSON.stringify({
                type: "cell_focus",
                cellId: cellId
            }));
        },
        
        // Send cell blur event via WebSocket
        sendCellBlur(row, column) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            const cellId = `${row}-${column}`;
            this.socket.send(JSON.stringify({
                type: "cell_blur",
                cellId: cellId
            }));
        },
        
        // Send cell edit event via WebSocket
        sendCellEdit(row, column, value) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            console.log(`Sending cell edit: [${row}, ${column}] = ${value}`);
            
            this.socket.send(JSON.stringify({
                type: "cell_edit",
                rowId: row,
                column: column,
                value: value
            }));
        },
        
        // Track mouse movement for cursor sharing
        trackMouseMovement() {
            if (!this.isCollaborative) return;
            
            let lastX = 0, lastY = 0;
            let throttled = false;
            
            document.addEventListener('mousemove', (e) => {
                if (throttled || !this.isConnected) return;
                throttled = true;
                
                // Only send if cursor moved significantly
                if (Math.abs(e.clientX - lastX) > 5 || Math.abs(e.clientY - lastY) > 5) {
                    lastX = e.clientX;
                    lastY = e.clientY;
                    
                    // Convert to cell-based positioning if possible
                    const tableRect = document.getElementById("data-table").getBoundingClientRect();
                    if (e.clientX >= tableRect.left && e.clientX <= tableRect.right &&
                        e.clientY >= tableRect.top && e.clientY <= tableRect.bottom) {
                        
                        // Send cursor position
                        this.socket.send(JSON.stringify({
                            type: "cursor_move",
                            cursor: {
                                x: e.clientX,
                                y: e.clientY
                            }
                        }));
                    }
                }
                
                setTimeout(() => { throttled = false; }, 50);
            });
        },
        
        // Update the display of a collaborator's cursor
        updateCursor(userId, cursor) {
            if (!this.collaborators[userId]) return;
            
            // Remove old cursor
            document.querySelectorAll(`.user-cursor[data-user-id="${userId}"]`).forEach(el => el.remove());
            
            // If cursor position is invalid, don't show it
            if (!cursor.x || !cursor.y) return;
            
            // Create cursor element
            const cursorElement = document.createElement("div");
            cursorElement.className = "user-cursor";
            cursorElement.setAttribute("data-user-id", userId);
            cursorElement.style.backgroundColor = this.collaborators[userId].color;
            
            // Add name tag to cursor
            const nameTag = document.createElement("div");
            nameTag.className = "cursor-name";
            nameTag.textContent = this.collaborators[userId].name;
            nameTag.style.backgroundColor = this.collaborators[userId].color;
            cursorElement.appendChild(nameTag);
            
            // Position the cursor
            cursorElement.style.left = `${cursor.x}px`;
            cursorElement.style.top = `${cursor.y}px`;
            
            // Add to DOM
            document.body.appendChild(cursorElement);
        },
        
        // Show a toast notification
        showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            
            const container = document.getElementById('toast-container') || document.body;
            container.appendChild(toast);
            
            setTimeout(() => toast.remove(), 2300);
        },
        
        // Generate a random color for the user
        getRandomColor() {
            const colors = [
                "#3b82f6", "#ef4444", "#10b981", "#f59e0b", 
                "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"
            ];
            return colors[Math.floor(Math.random() * colors.length)];
        },
        
        // Shut down the server
        async shutdownServer() {
            if (!confirm('Are you sure you want to send the data back and close the editor connection?')) return;
            
            try {
                await this.saveData();
                const response = await fetch('/shutdown', {method: 'POST'});
                if (response.ok) {
                    this.showToast('Server shutting down...', 'success');
                    setTimeout(() => {
                        if (window.parent !== window) {
                            window.parent.document.querySelector('iframe').remove();
                        } else {
                            window.close();
                        }
                    }, 1000);
                } else {
                    throw new Error('Shutdown request failed');
                }
            } catch (e) {
                console.error('Error shutting down:', e);
                this.showToast('Error shutting down server', 'error');
            }
        },
        
        // Cancel changes and close the editor
        async cancelChanges() {
            if (!confirm('Are you sure you want to discard all changes and close the editor?')) return;
            
            try {
                const response = await fetch('/cancel', { method: 'POST' });
                
                if (response.ok) {
                    this.showToast('Discarding changes...', 'success');
                    setTimeout(() => {
                        if (window.parent !== window) {
                            window.parent.document.querySelector('iframe').remove();
                        } else {
                            window.close();
                        }
                    }, 1000);
                } else {
                    throw new Error('Cancel request failed');
                }
            } catch (e) {
                console.error('Error canceling:', e);
                this.showToast('Error canceling changes', 'error');
            }
        }
    };
}
