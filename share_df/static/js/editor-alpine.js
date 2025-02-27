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
            
            const self = this; // Store reference to 'this' for callbacks
            
            // Define common cell callbacks for all columns
            const cellCallbacks = {
                // When user hovers over a cell, track it for other users
                cellMouseEnter: function(e, cell) {
                    if (!self.isCollaborative || !self.isConnected) return;
                    
                    const row = cell.getRow().getPosition();
                    const column = cell.getColumn().getField();
                    
                    // Send hover position to server with cell coordinates
                    self.sendCursorPosition(row, column);
                },
                
                // Editing callbacks already implemented in setupCellEvents(),
                // But we'll enhance them for better visibility
            };
            
            // Apply these callbacks to all columns
            const columns = Object.keys(this.tableData[0]).map(key => ({
                title: key,
                field: key,
                editor: true,
                headerClick: (e, column) => this.editColumnHeader(e, column),
                ...cellCallbacks
            }));
            
            // Initialize table with the enhanced columns
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
                },
                cellEdited: function(cell) {
                    // This captures ALL cell edits across the table
                    const row = cell.getRow().getPosition();
                    const column = cell.getColumn().getField();
                    const value = cell.getValue();
                    
                    console.log(`Global cell edit: [${row}, ${column}] = ${value}`);
                    
                    // Update local data model
                    self.tableData = self.table.getData();
                    
                    // Send to server
                    if (self.isCollaborative && self.isConnected) {
                        self.sendCellEdit(row, column, value);
                    }
                },
                dataChanged: function(data) {
                    // Capture structural changes to the table data
                    if (self.isCollaborative && self.isConnected) {
                        self.sendTableUpdate(data);
                    }
                },
                columnMoved: function(column, columns) {
                    // Capture column reordering
                    if (self.isCollaborative && self.isConnected) {
                        const columnOrder = columns.map(col => col.getField());
                        self.sendColumnReorder(columnOrder);
                    }
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
            
            // Broadcast the column addition to other collaborators
            if (this.isCollaborative && this.isConnected) {
                console.log(`Broadcasting add column: ${newColumnName}`);
                this.socket.send(JSON.stringify({
                    type: "add_column",
                    columnName: newColumnName
                }));
            }
        },
        
        // Add a new row to the table
        addNewRow() {
            const columns = this.table.getColumns();
            const newRow = {};
            columns.forEach(column => {
                newRow[column.getField()] = '';
            });
            
            // Add row to our table
            const addedRow = this.table.addRow(newRow);
            const rowId = addedRow.getPosition();
            
            // Broadcast the row addition to other collaborators
            if (this.isCollaborative && this.isConnected) {
                console.log(`Broadcasting add row at position: ${rowId}`);
                this.socket.send(JSON.stringify({
                    type: "add_row",
                    rowId: rowId
                }));
            }
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
                    
                case "cursor_position":
                    // A user moved their cursor to a specific cell
                    if (message.userId !== this.userId && message.position) {
                        this.highlightCellForUser(message.userId, message.position.row, message.position.column);
                    }
                    break;
                    
                case "table_structure":
                    // Table structure changed (e.g., columns added/removed)
                    if (message.userId !== this.userId) {
                        console.log("Received table structure update");
                        this.syncTableStructure(message.columns, message.rowCount);
                    }
                    break;
                    
                case "column_reorder":
                    // Column order changed
                    if (message.userId !== this.userId && message.columns) {
                        console.log("Applying column reorder");
                        this.reorderColumns(message.columns);
                    }
                    break;
                    
                case "add_column":
                    // Another user added a column
                    if (message.userId !== this.userId && message.columnName) {
                        console.log(`Adding column from remote: ${message.columnName}`);
                        
                        // Add the column to our table
                        this.table.addColumn({
                            title: message.columnName,
                            field: message.columnName,
                            editor: true,
                            headerClick: (e, column) => this.editColumnHeader(e, column)
                        }, false);
                        
                        // Update our column count to stay in sync
                        const columnCount = parseInt(message.columnName.replace('New Column ', ''));
                        if (!isNaN(columnCount) && columnCount > this.columnCount) {
                            this.columnCount = columnCount;
                        }
                        
                        this.showToast(`${this.collaborators[message.userId]?.name || 'Someone'} added column: ${message.columnName}`);
                    }
                    break;
                    
                case "add_row":
                    // Another user added a row
                    if (message.userId !== this.userId) {
                        console.log(`Adding row from remote at position: ${message.rowId}`);
                        
                        // Create a new empty row with the same structure as existing rows
                        const columns = this.table.getColumns();
                        const newRow = {};
                        columns.forEach(column => {
                            newRow[column.getField()] = '';
                        });
                        
                        // Add the row to our table
                        this.table.addRow(newRow);
                        
                        this.showToast(`${this.collaborators[message.userId]?.name || 'Someone'} added a new row`);
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
            if (!this.isCollaborative || !this.socket === null) return;
            
            let lastX = 0, lastY = 0;
            let throttled = false;
            
            document.addEventListener('mousemove', (e) => {
                if (throttled || !this.isConnected) return;
                throttled = true;
                
                // Only send if cursor moved significantly
                if (Math.abs(e.clientX - lastX) > 5 || Math.abs(e.clientY - lastY) > 5) {
                    lastX = e.clientX;
                    lastY = e.clientY;
                    
                    // Send absolute cursor position (this was working before)
                    this.socket.send(JSON.stringify({
                        type: "cursor_move",
                        cursor: {
                            x: e.clientX,
                            y: e.clientY
                        }
                    }));
                    
                    // Also check if cursor is over a cell for cell-based tracking
                    const tableRect = document.getElementById("data-table").getBoundingClientRect();
                    if (e.clientX >= tableRect.left && e.clientX <= tableRect.right &&
                        e.clientY >= tableRect.top && e.clientY <= tableRect.bottom) {
                        
                        // Try to find the cell under the cursor
                        const cellElements = document.querySelectorAll('.tabulator-cell');
                        for (const cellEl of cellElements) {
                            const rect = cellEl.getBoundingClientRect();
                            if (e.clientX >= rect.left && e.clientX <= rect.right &&
                                e.clientY >= rect.top && e.clientY <= rect.bottom) {
                                
                                // Found the cell - get its row and column
                                const row = this.table.getRowFromPosition(
                                    this.table.rowManager.getRowFromElement(cellEl).getIndex()
                                );
                                const column = this.table.columnManager.getColumnFromElement(cellEl);
                                
                                if (row && column) {
                                    this.sendCursorPosition(row.getPosition(), column.getField());
                                }
                                break;
                            }
                        }
                    }
                }
                
                setTimeout(() => { throttled = false; }, 50);
            });
        },
        
        // Replace cursor movement tracking with cell-based position tracking
        sendCursorPosition(row, column) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            this.socket.send(JSON.stringify({
                type: "cursor_position",
                position: {
                    row: row,
                    column: column
                }
            }));
        },
        
        // Update the display of a collaborator's cursor
        updateCursor(userId, cursor) {
            if (!this.collaborators[userId] || !cursor.x || !cursor.y) return;
            
            // Remove old cursor
            document.querySelectorAll(`.user-cursor-absolute[data-user-id="${userId}"]`).forEach(el => el.remove());
            
            // Create cursor element
            const cursorElement = document.createElement("div");
            cursorElement.className = "user-cursor-absolute";
            cursorElement.setAttribute("data-user-id", userId);
            
            const userName = this.collaborators[userId].name || "User";
            const userColor = this.collaborators[userId].color || "#3b82f6";
            
            // Style the cursor element
            cursorElement.style.position = "fixed";
            cursorElement.style.left = `${cursor.x}px`;
            cursorElement.style.top = `${cursor.y}px`;
            cursorElement.style.width = "12px";
            cursorElement.style.height = "12px";
            cursorElement.style.backgroundColor = userColor;
            cursorElement.style.borderRadius = "50%";
            cursorElement.style.pointerEvents = "none";
            cursorElement.style.zIndex = "9999";
            cursorElement.style.transition = "transform 0.1s ease";
            cursorElement.style.transform = "translate(-50%, -50%)";
            
            // Add name tag to cursor
            const nameTag = document.createElement("div");
            nameTag.className = "cursor-name";
            nameTag.textContent = userName;
            nameTag.style.backgroundColor = userColor;
            nameTag.style.position = "absolute";
            nameTag.style.top = "-20px";
            nameTag.style.left = "0";
            nameTag.style.color = "white";
            nameTag.style.fontSize = "10px";
            nameTag.style.padding = "2px 4px";
            nameTag.style.borderRadius = "2px";
            nameTag.style.whiteSpace = "nowrap";
            nameTag.style.transform = "translateX(-50%)";
            nameTag.style.userSelect = "none";
            
            cursorElement.appendChild(nameTag);
            document.body.appendChild(cursorElement);
            
            // Remove cursor after inactivity
            setTimeout(() => {
                if (cursorElement.parentNode) {
                    cursorElement.style.opacity = "0.5";
                }
            }, 5000);
        },
        
        // Add a method to send table structure updates
        sendTableUpdate(data) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            console.log("Sending table update");
            
            // Only send the structure, not all data (could be too large)
            const columnInfo = this.table.getColumns().map(col => ({
                field: col.getField(),
                title: col.getDefinition().title
            }));
            
            this.socket.send(JSON.stringify({
                type: "table_structure",
                columns: columnInfo,
                rowCount: data.length
            }));
        },
        
        // Add a method to send column reordering information
        sendColumnReorder(columnOrder) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            console.log("Sending column reorder:", columnOrder);
            
            this.socket.send(JSON.stringify({
                type: "column_reorder",
                columns: columnOrder
            }));
        },
        
        // Add method to highlight a cell when another user is hovering over it
        highlightCellForUser(userId, row, column) {
            if (!this.collaborators[userId]) return;
            
            // Remove any existing cursor indicators
            document.querySelectorAll(`.user-cursor[data-user-id="${userId}"]`).forEach(el => el.remove());
            
            try {
                // Find the cell
                const cell = this.table.getCell(row, column);
                if (!cell || !cell.getElement()) return;
                
                const cellElement = cell.getElement();
                const cellRect = cellElement.getBoundingClientRect();
                const userName = this.collaborators[userId].name || "User";
                const userColor = this.collaborators[userId].color || "#3b82f6";
                
                // Create a highlight element
                const highlightEl = document.createElement("div");
                highlightEl.className = "user-cursor";
                highlightEl.setAttribute("data-user-id", userId);
                highlightEl.style.position = "absolute";
                highlightEl.style.left = `${cellRect.left}px`;
                highlightEl.style.top = `${cellRect.top}px`;
                highlightEl.style.width = `${cellRect.width}px`;
                highlightEl.style.height = `${cellRect.height}px`;
                highlightEl.style.border = `2px solid ${userColor}`;
                highlightEl.style.backgroundColor = `${userColor}20`; // 20% opacity
                highlightEl.style.zIndex = "100";
                highlightEl.style.pointerEvents = "none";
                
                // Add name tag
                const nameTag = document.createElement("div");
                nameTag.className = "cursor-name";
                nameTag.textContent = userName;
                nameTag.style.backgroundColor = userColor;
                nameTag.style.color = "white";
                nameTag.style.position = "absolute";
                nameTag.style.top = "-20px";
                nameTag.style.left = "0";
                nameTag.style.fontSize = "10px";
                nameTag.style.padding = "2px 4px";
                nameTag.style.borderRadius = "2px";
                
                highlightEl.appendChild(nameTag);
                document.body.appendChild(highlightEl);
                
                // Auto-remove after a short delay
                setTimeout(() => {
                    if (highlightEl.parentNode) {
                        highlightEl.remove();
                    }
                }, 2000);
            } catch (e) {
                console.error("Error highlighting cell:", e);
            }
        },
        
        // Add method to sync table structure when it changes
        syncTableStructure(columns, rowCount) {
            if (!this.table) return;
            
            // Get current data
            const currentData = this.table.getData();
            
            // Get current column definitions
            const currentColumns = this.table.getColumns().map(col => ({
                field: col.getField(),
                title: col.getDefinition().title
            }));
            
            // Check if we need to add columns
            const newColumnDefs = [];
            
            columns.forEach(newCol => {
                const existingCol = currentColumns.find(col => col.field === newCol.field);
                if (!existingCol) {
                    // This is a new column
                    newColumnDefs.push({
                        title: newCol.title,
                        field: newCol.field,
                        editor: true
                    });
                }
            });
            
            // Add any new columns
            if (newColumnDefs.length > 0) {
                newColumnDefs.forEach(colDef => {
                    this.table.addColumn(colDef);
                });
            }
            
            // Add any missing rows
            const currentRowCount = currentData.length;
            if (rowCount > currentRowCount) {
                // Need to add rows
                const newRows = [];
                const columnFields = this.table.getColumns().map(col => col.getField());
                
                for (let i = currentRowCount; i < rowCount; i++) {
                    const newRow = {};
                    columnFields.forEach(field => {
                        newRow[field] = "";
                    });
                    newRows.push(newRow);
                }
                
                if (newRows.length > 0) {
                    this.table.addData(newRows);
                }
            }
        },
        
        // Add method to reorder columns when they're moved
        reorderColumns(columnOrder) {
            if (!this.table) return;
            
            // Get current columns
            const currentColumns = this.table.getColumns();
            const columnMap = {};
            
            // Create a map of field -> column
            currentColumns.forEach(col => {
                columnMap[col.getField()] = col.getDefinition();
            });
            
            // Create new column definitions in the right order
            const newColumnDefs = columnOrder.map(field => {
                if (columnMap[field]) {
                    return columnMap[field];
                }
                return null;
            }).filter(Boolean);
            
            // Apply the new column order
            if (newColumnDefs.length > 0) {
                this.table.setColumns(newColumnDefs);
            }
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
