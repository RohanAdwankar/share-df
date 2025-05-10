function editorApp(isCollaborative, isTestMode = false) {
    return {
        // Add isTestMode to state variables
        table: null,
        isCollaborative,
        isTestMode,
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
        _messageCache: {},
        _lastActionId: null,
        
        // Version history related state
        isVersionHistorySidebarOpen: false,
        expandedSnapshots: [],
        versionSnapshots: [],
        versionChanges: [],
        snapshotContextMenu: { visible: false, x: 0, y: 0, snapshotId: null },
        changeContextMenu: { visible: false, x: 0, y: 0, changeId: null },
        versionHistoryInterval: null,
        
        // Initialize the application
        async init() {
            this.userColor = this.getRandomColor();
            await this.loadData();
            this.initializeTable();
            
            if (this.isCollaborative) {
                this.setupWebSocket();
                
                // Load initial version history data for collaborative mode
                if (this.isVersionHistorySidebarOpen) {
                    this.loadVersionHistory();
                }
                
                // Set up cleanup on page unload for version history tracking
                window.addEventListener('beforeunload', () => {
                    // Create a final snapshot before leaving if in collaborative mode
                    if (this.socket && this.isConnected) {
                        // Use sendBeacon for reliable delivery during page unload
                        navigator.sendBeacon('/create_snapshot', JSON.stringify({
                            manual: false,
                            user_id: this.userId,
                            user_name: this.userName,
                            event: 'page_unload'
                        }));
                    }
                });
            }
            
            // Only show tooltip in non-test mode
            if (!this.isTestMode) {
                setTimeout(() => {
                    const tooltip = document.getElementById('column-rename-tooltip');
                    if (tooltip) {
                        tooltip.style.display = 'block';
                        
                        // Auto-hide after 10 seconds
                        setTimeout(() => {
                            tooltip.style.display = 'none';
                        }, 10000);
                        
                        // Handle dismiss button
                        document.getElementById('dismiss-tooltip')?.addEventListener('click', () => {
                            tooltip.style.display = 'none';
                        });
                    }
                }, 2000);
            }
            setupTooltip();
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
            if (this.tableData.length === 0) return;
            
            const self = this; // Store reference to 'this' for callbacks
            
            // Apply callbacks to all columns
            const columns = Object.keys(this.tableData[0]).map(key => ({
                title: key,
                field: key,
                editor: true,
                sorter: "string", // Default sorter
                // Use headerClick with shift key check
                headerClick: (e, column) => {
                    // If shift key is pressed, rename column, otherwise let default sort behavior happen
                    if (e.shiftKey) {
                        e.stopPropagation(); // Stop the default sort behavior
                        this.editColumnHeader(e, column);
                        return false; // Prevent default behavior
                    }
                    // Let default sort behavior happen for regular clicks
                    return true;
                },
                cellMouseEnter: function(e, cell) {
                    if (!self.isCollaborative || !self.isConnected) return;
                    
                    // Convert 1-based to 0-based row position
                    const row = cell.getRow().getPosition() - 1;
                    const column = cell.getColumn().getField();
                    
                    self.sendCursorPosition(row, column);
                }
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
                    // Convert 1-based to 0-based row position
                    const row = cell.getRow().getPosition() - 1;
                    const column = cell.getColumn().getField();
                    const value = cell.getValue();
                    
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
        
        // Save and continue editing (for collaborative mode)
        async saveAndContinue() {
            try {
                if (!this.table) return;
                const data = this.table.getData();
                const response = await fetch('/save_and_continue', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({data}),
                });
                
                if (!response.ok) {
                    throw new Error(`Failed to save: ${response.statusText}`);
                }
                
                const result = await response.json();
                
                // Show success message
                this.showToast('Changes saved successfully! You can continue editing.');
                
                // Broadcast to other users that data was saved
                if (this.isConnected && this.socket) {
                    this.socket.send(JSON.stringify({
                        type: "data_sync",
                        message: "Data has been saved by " + this.userName
                    }));
                }
                
                // Create a version snapshot if it doesn't exist yet
                if (this.isCollaborative && this.isConnected && this.socket) {
                    this.socket.send(JSON.stringify({
                        type: "create_snapshot",
                        message: "Manual save by " + this.userName
                    }));
                }
                
            } catch (e) {
                console.error('Error saving data:', e);
                this.showToast('Error saving data: ' + e.message, 'error');
            }
        },
        
        // Add a new column to the table
        addNewColumn() {
            this._lastActionId = `col_${Date.now()}`;
            
            this.columnCount++;
            const newColumnName = `New Column ${this.columnCount}`;
            
            this.table.addColumn({
                title: newColumnName,
                field: newColumnName,
                editor: true,
                sorter: "string", // Default sorter
                // Use headerClick with shift key check
                headerClick: (e, column) => {
                    // If shift key is pressed, rename column, otherwise let default sort behavior happen
                    if (e.shiftKey) {
                        e.stopPropagation(); // Stop the default sort behavior
                        this.editColumnHeader(e, column);
                        return false; // Prevent default behavior
                    }
                    // Let default sort behavior happen for regular clicks
                    return true;
                },
                cellMouseEnter: (e, cell) => {
                    if (this.isCollaborative && this.isConnected) {
                        // Convert 1-based to 0-based row position
                        const row = cell.getRow().getPosition() - 1;
                        const column = cell.getColumn().getField();
                        this.sendCursorPosition(row, column);
                    }
                }
            }, false);
            
            // Broadcast the column addition to other collaborators
            if (this.isCollaborative && this.isConnected) {
                this.socket.send(JSON.stringify({
                    type: "add_column",
                    columnName: newColumnName,
                    actionId: this._lastActionId
                }));
            }
        },
        
        // Add a new row to the table
        addNewRow() {
            this._lastActionId = `row_${Date.now()}`;
            
            const columns = this.table.getColumns();
            const newRow = {};
            columns.forEach(column => {
                newRow[column.getField()] = '';
            });
            
            // Add row to our table - using a simpler direct update for reliability
            const currentData = this.table.getData();
            currentData.push(newRow);
            this.table.setData(currentData);
            
            // Get the position - it's the last row (0-based)
            const rowPosition = currentData.length - 1;
            
            // Broadcast the row addition to other collaborators
            if (this.isCollaborative && this.isConnected) {
                this.socket.send(JSON.stringify({
                    type: "add_row",
                    rowId: rowPosition,
                    actionId: this._lastActionId
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
            // First, clear any existing connection
            if (this.socket) {
                this.socket.onmessage = null;
                this.socket.onclose = null;
                this.socket.onerror = null;
                this.socket.close();
                this.socket = null;
            }
            
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            const wsUrl = `${protocol}${window.location.host}/ws`;
            
            this.socket = new WebSocket(wsUrl);
            
            // Set flag to ensure we only ask for username once
            let userNamePromptShown = false;
            
            this.socket.onopen = (e) => {
                this.isConnected = true;
                
                // Ask for user name when first connecting, but only once
                if (!userNamePromptShown) {
                    userNamePromptShown = true;
                    const name = prompt("Enter your name for collaboration:", this.userName) || this.userName;
                    this.userName = name;
                    
                    // Send user info to server
                    this.socket.send(JSON.stringify({
                        type: "update_user",
                        name: this.userName,
                        color: this.userColor
                    }));
                }
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (e) {
                    console.error("Error handling WebSocket message:", e);
                }
            };
            
            this.socket.onclose = (event) => {
                this.isConnected = false;
                
                if (event.wasClean) {
                    this.showToast(`Connection closed: ${event.reason}`, 'error');
                } else {
                    // Connection died
                    this.showToast("Closing the connection!", 'error');
                }
            };
            
            this.socket.onerror = (error) => {
                console.error("WebSocket error:", error);
                this.showToast("WebSocket error occurred", 'error');
            };
            
            // Track mouse movement for cursor sharing
            this.trackMouseMovement();
        },
        
        // Simplified message deduplication
        _deduplicateMessage(message) {
            // Create a signature for this message to detect duplicates
            let signature = `${message.type}:`;
            
            if (message.type === 'add_column') {
                signature += message.columnName;
            } else if (message.type === 'add_row') {
                signature += message.rowId;
            } else if (message.type === 'cell_edit') {
                signature += `${message.rowId}:${message.column}:${message.value}`;
            } else if (message.type === 'cursor_position') {
                // Skip deduplication for cursor movements
                return false;
            } else {
                return false;
            }
            
            const now = Date.now();
            
            // Check if we've seen this message recently
            if (this._messageCache[signature] && now - this._messageCache[signature] < 300) {
                return true; // Duplicate found
            }
            
            // Store this message in the cache
            this._messageCache[signature] = now;
            
            // Clean up old cache entries - only if cache is getting large
            if (Object.keys(this._messageCache).length > 100) {
                const cutoff = now - 2000; // 2 seconds
                for (const key in this._messageCache) {
                    if (this._messageCache[key] < cutoff) {
                        delete this._messageCache[key];
                    }
                }
            }
            
            return false;
        },
        
        // Handle incoming WebSocket messages
        handleWebSocketMessage(message) {
            // Skip duplicates
            if (this._deduplicateMessage(message)) return;
            
            // Protect against own actions
            if (message.actionId && message.actionId === this._lastActionId) return;
            
            switch (message.type) {
                case "init":
                    this.userId = message.userId;
                    
                    message.collaborators.forEach(user => {
                        if (user.id !== this.userId) {
                            this.collaborators[user.id] = user;
                        }
                    });
                    
                    // CRITICAL FIX: Always use server's current data if it exists
                    if (message.currentData && Array.isArray(message.currentData) && message.currentData.length > 0) {
                        console.log("Received current data from server with:", 
                            message.currentData.length, "rows and columns:", 
                            Object.keys(message.currentData[0] || {}).join(", "));
                        
                        // Always use the server's data which includes all columns and all rows
                        this.tableData = message.currentData;
                        
                        // Update column count if needed
                        if (message.addedColumns && Array.isArray(message.addedColumns)) {
                            message.addedColumns.forEach(colName => {
                                const columnNumber = parseInt(colName.replace('New Column ', ''));
                                if (!isNaN(columnNumber) && columnNumber > this.columnCount) {
                                    this.columnCount = columnNumber;
                                }
                            });
                        }
                        
                        // If table is already initialized, completely rebuild it with the current data
                        if (this.table) {
                            console.log("Rebuilding table with current server data");
                            
                            // Capture current column settings
                            const existingColumns = this.table.getColumns().map(col => ({
                                field: col.getField(),
                                title: col.getDefinition().title
                            }));
                            
                            // Define all columns, including ones from current data
                            let allColumns = Object.keys(this.tableData[0] || {}).map(key => {
                                const existingCol = existingColumns.find(col => col.field === key);
                                return {
                                    title: existingCol?.title || key,
                                    field: key,
                                    editor: true,
                                    sorter: "string",
                                    headerClick: (e, column) => {
                                        if (e.shiftKey) {
                                            e.stopPropagation();
                                            this.editColumnHeader(e, column);
                                            return false;
                                        }
                                        return true;
                                    },
                                    cellMouseEnter: (e, cell) => {
                                        if (this.isCollaborative && this.isConnected) {
                                            const row = cell.getRow().getPosition() - 1;
                                            const column = cell.getColumn().getField();
                                            this.sendCursorPosition(row, column);
                                        }
                                    }
                                };
                            });
                            
                            // Completely rebuild table with all current data
                            this.table.setColumns(allColumns);
                            this.table.setData(this.tableData);
                        }
                    }
                    break;
                    
                case "user_joined":
                    this.showToast(`${message.name || "A new user"} joined the session`, 'success');
                    break;
                    
                case "user_update":
                    if (message.user && message.user.id !== this.userId) {
                        this.collaborators[message.user.id] = message.user;
                        
                        // Show toast for first update from a user
                        if (!document.querySelector(`.collaborator-badge[data-user-id="${message.user.id}"]`)) {
                            this.showToast(`${message.user.name} joined the session`, 'success');
                        }
                    }
                    break;
                    
                case "user_left":
                    if (message.userId && this.collaborators[message.userId]) {
                        const userName = this.collaborators[message.userId].name;
                        delete this.collaborators[message.userId];
                        
                        // Remove any cursors for this user
                        document.querySelectorAll(`.user-cursor[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                        document.querySelectorAll(`.user-cursor-absolute[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                        
                        this.showToast(`${userName} left the session`, 'error');
                    }
                    break;
                    
                case "cell_focus":
                    // Another user is focusing on a cell
                    if (message.userId !== this.userId) {
                        const cellId = message.cellId;
                        const [rowId, colField] = cellId.split("-");
                        
                        try {
                            // Get the row first
                            const rows = this.table.getRows();
                            if (rows && rowId < rows.length) {
                                const row = rows[rowId];
                                if (row) {
                                    const cell = row.getCell(colField);
                                    if (cell && cell.getElement()) {
                                        const userName = this.collaborators[message.userId]?.name || "User";
                                        const userColor = this.collaborators[message.userId]?.color || "#3b82f6";
                                        
                                        // Mark the cell as being edited
                                        const element = cell.getElement();
                                        element.classList.add("cell-being-edited");
                                        element.style.boxShadow = `0 0 0 2px ${userColor} inset`;
                                        
                                        // Add editor name
                                        const nameTag = document.createElement("div");
                                        nameTag.className = "editor-name";
                                        nameTag.textContent = userName;
                                        nameTag.style.backgroundColor = userColor;
                                        nameTag.style.color = "#ffffff";
                                        element.appendChild(nameTag);
                                    }
                                }
                            }
                        } catch (e) {
                            console.error("Error handling cell focus:", e);
                        }
                    }
                    break;
                    
                case "cell_blur":
                    // User stopped editing a cell
                    if (message.userId !== this.userId) {
                        const cellId = message.cellId;
                        const [rowId, colField] = cellId.split("-");
                        
                        try {
                            const rows = this.table.getRows();
                            if (rows && rowId < rows.length) {
                                const row = rows[rowId];
                                if (row) {
                                    const cell = row.getCell(colField);
                                    if (cell && cell.getElement()) {
                                        const element = cell.getElement();
                                        element.classList.remove("cell-being-edited");
                                        element.style.boxShadow = "";
                                        
                                        // Remove editor name
                                        const nameTag = element.querySelector(".editor-name");
                                        if (nameTag) nameTag.remove();
                                    }
                                }
                            }
                        } catch (e) {
                            console.error("Error handling cell blur:", e);
                        }
                    }
                    break;
                    
                case "cell_edit":
                    // Another user edited a cell
                    if (message.userId !== this.userId) {
                        const rowId = message.rowId;
                        const column = message.column;
                        const value = message.value;
                        
                        try {
                            // Ensure the column exists before attempting to edit its value
                            if (this.table) {
                                const existingColumns = this.table.getColumns().map(col => col.getField());
                                
                                if (!existingColumns.includes(column)) {
                                    // Add the missing column first
                                    console.log(`Adding missing column ${column} before editing cell`);
                                    
                                    const columnNumber = parseInt(column.replace('New Column ', ''));
                                    if (!isNaN(columnNumber) && columnNumber > this.columnCount) {
                                        this.columnCount = columnNumber;
                                    }
                                    
                                    this.table.addColumn({
                                        title: column,
                                        field: column,
                                        editor: true,
                                        sorter: "string",
                                        headerClick: (e, column) => {
                                            if (e.shiftKey) {
                                                e.stopPropagation();
                                                this.editColumnHeader(e, column);
                                                return false;
                                            }
                                            return true;
                                        },
                                        cellMouseEnter: (e, cell) => {
                                            if (this.isCollaborative && this.isConnected) {
                                                const row = cell.getRow().getPosition() - 1;
                                                const column = cell.getColumn().getField();
                                                this.sendCursorPosition(row, column);
                                            }
                                        }
                                    }, false);
                                }
                                
                                // Get the current data
                                const allData = this.table.getData();
                                
                                // Ensure the row exists
                                if (rowId >= allData.length) {
                                    console.log(`Row ${rowId} doesn't exist, adding empty rows`);
                                    
                                    // Add missing rows with empty values
                                    const columns = this.table.getColumns();
                                    const emptyRows = [];
                                    
                                    for (let i = allData.length; i <= rowId; i++) {
                                        const newRow = {};
                                        columns.forEach(col => {
                                            newRow[col.getField()] = '';
                                        });
                                        emptyRows.push(newRow);
                                    }
                                    
                                    // Add the rows
                                    this.table.addData(emptyRows);
                                    
                                    // Refresh allData
                                    const updatedData = this.table.getData();
                                    
                                    // Now set the value
                                    if (rowId < updatedData.length) {
                                        updatedData[rowId][column] = value;
                                        
                                        // Update the table with the full updated data
                                        this.table.setData(updatedData);
                                    }
                                } else {
                                    // Row exists, just update the cell
                                    allData[rowId][column] = value;
                                    this.table.updateData(allData);
                                    
                                    // Also attempt direct DOM update for visual feedback
                                    const cellElements = document.querySelectorAll(`.tabulator-cell[tabulator-field="${column}"]`);
                                    if (cellElements && cellElements.length > rowId) {
                                        const cellElement = cellElements[rowId];
                                        if (cellElement) {
                                            cellElement.innerText = value;
                                            cellElement.style.backgroundColor = "rgba(59, 130, 246, 0.3)";
                                            setTimeout(() => {
                                                cellElement.style.backgroundColor = "";
                                            }, 1000);
                                        }
                                    }
                                }
                                
                                // Update our local data model
                                this.tableData = this.table.getData();
                            }
                        } catch (e) {
                            console.error("Error updating cell:", e);
                            // Last resort: reload the entire table
                            this.loadData().then(data => {
                                if (data && data.length > 0) {
                                    this.table.setData(data);
                                }
                            });
                        }
                    }
                    break;
                    
                case "cursor_position":
                    // A user moved their cursor to a specific cell
                    if (message.userId !== this.userId && message.position) {
                        this.highlightCellForUser(message.userId, message.position.row, message.position.column);
                    }
                    break;
                    
                case "table_structure":
                    // Table structure changed
                    if (message.userId !== this.userId) {
                        this.syncTableStructure(message.columns, message.rowCount);
                    }
                    break;
                    
                case "column_reorder":
                    // Column order changed
                    if (message.userId !== this.userId && message.columns) {
                        this.reorderColumns(message.columns);
                    }
                    break;
                    
                case "add_column":
                    // Another user added a column
                    if (message.userId !== this.userId) {
                        const columnName = message.columnName;
                        
                        try {
                            console.log(`Adding new column '${columnName}' from user ${message.userId}`);
                            
                            // Check if column already exists to avoid duplicates
                            const existingColumns = this.table.getColumns().map(col => col.getField());
                            if (existingColumns.includes(columnName)) {
                                console.log(`Column '${columnName}' already exists, skipping`);
                                return;
                            }
                            
                            // Add the column to our table
                            this.table.addColumn({
                                title: columnName,
                                field: columnName,
                                editor: true,
                                sorter: "string", 
                                headerClick: (e, column) => {
                                    if (e.shiftKey) {
                                        e.stopPropagation();
                                        this.editColumnHeader(e, column);
                                        return false;
                                    }
                                    return true;
                                },
                                cellMouseEnter: (e, cell) => {
                                    if (this.isCollaborative && this.isConnected) {
                                        const row = cell.getRow().getPosition() - 1;
                                        const column = cell.getColumn().getField();
                                        this.sendCursorPosition(row, column);
                                    }
                                }
                            }, false);
                            
                            // Update our column count
                            const columnCount = parseInt(columnName.replace('New Column ', ''));
                            if (!isNaN(columnCount) && columnCount > this.columnCount) {
                                this.columnCount = columnCount;
                            }
                            
                            // Update our local data model
                            this.tableData = this.table.getData();
                            
                            this.showToast(`${this.collaborators[message.userId]?.name || 'Someone'} added column: ${columnName}`);
                        } catch (e) {
                            console.error(`Failed to add column '${columnName}':`, e);
                        }
                    }
                    break;
                    
                case "add_row":
                    // Another user added a row
                    if (message.userId !== this.userId) {
                        try {
                            // Create a new empty row with all existing columns
                            const columns = this.table.getColumns();
                            const newRow = {};
                            columns.forEach(column => {
                                newRow[column.getField()] = '';
                            });
                            
                            console.log(`Adding new row from user ${message.userId}`);
                            
                            // Add the row with a better approach
                            this.table.addRow(newRow);
                            
                            // Update our local data model
                            this.tableData = this.table.getData();
                            
                            this.showToast(`${this.collaborators[message.userId]?.name || 'Someone'} added a new row`);
                        } catch (e) {
                            console.error("Failed to add row:", e);
                        }
                    }
                    break;

                case "data_sync":
                    // Another user has saved their changes
                    this.showToast(message.message || 'Data has been synchronized', 'success');
                    
                    // Optionally reload data to ensure consistency
                    if (message.reload) {
                        this.loadData().then(data => {
                            if (data && data.length > 0) {
                                this.table.setData(data);
                            }
                        });
                    }
                    break;

                case "user_finished":
                    // Another user has finished their session
                    if (message.userId !== this.userId) {
                        const userName = this.collaborators[message.userId]?.name || "A user";
                        this.showToast(`${userName} has finished editing`, 'info');
                        
                        // Remove them from collaborators list
                        if (this.collaborators[message.userId]) {
                            delete this.collaborators[message.userId];
                        }
                        
                        // Remove any cursors for this user
                        document.querySelectorAll(`.user-cursor[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                        document.querySelectorAll(`.user-cursor-absolute[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                    }
                    break;

                case "dtype_error":
                    // Handle dtype validation error
                    this.handleDtypeError(message);
                    break;
                    
                case "version_change":
                    // A new version change event happened
                    if (message.change) {
                        const isNewChange = !this.versionChanges.some(change => change.id === message.change.id);
                        
                        if (isNewChange) {
                            // Add to our changes list
                            this.versionChanges.push(message.change);
                            
                            // Only show toast if version history sidebar is open
                            if (this.isVersionHistorySidebarOpen) {
                                const userName = message.change.user_name || "Someone";
                                const changeType = message.change.change_type || "unknown";
                                this.showToast(`${userName} made a ${changeType} change`, 'info');
                            }
                        }
                    }
                    break;
                    
                case "version_snapshot":
                    // A new version snapshot was created
                    if (message.snapshot) {
                        const isNewSnapshot = !this.versionSnapshots.some(snapshot => snapshot.id === message.snapshot.id);
                        
                        if (isNewSnapshot) {
                            // Add to our snapshots list
                            this.versionSnapshots.push(message.snapshot);
                            
                            // Sort snapshots by timestamp in descending order
                            this.versionSnapshots.sort((a, b) => b.timestamp - a.timestamp);
                            
                            // Only show toast if version history sidebar is open
                            if (this.isVersionHistorySidebarOpen) {
                                this.showToast("New version snapshot created", 'info');
                            }
                        }
                    }
                    break;

                case "version_restored":
                    // Someone restored to a previous version
                    if (message.userId !== this.userId) {
                        // Show notification about who restored
                        const userName = this.collaborators[message.userId]?.name || "Someone";
                        this.showToast(`${userName} restored to a previous version`, 'info');
                        
                        // Reload data to get the restored version
                        this.loadData().then(data => {
                            if (data && data.length > 0) {
                                this.table.setData(data);
                                this.tableData = data;
                            }
                        });
                    }
                    break;

                case "user_cancelled":
                    // Another user has cancelled their changes
                    if (message.userId !== this.userId) {
                        const userName = message.userName || this.collaborators[message.userId]?.name || "A user";
                        this.showToast(`${userName} has discarded their changes and left`, 'info');
                        
                        // Remove them from collaborators list
                        if (this.collaborators[message.userId]) {
                            delete this.collaborators[message.userId];
                        }
                        
                        // Remove any cursors for this user
                        document.querySelectorAll(`.user-cursor[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                        document.querySelectorAll(`.user-cursor-absolute[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                    }
                    break;
            }
        },
        
        // Handle dtype validation errors
        handleDtypeError(message) {
            const { rowId, column, value, expected_dtype, message: errorMsg } = message;
            
            // Show error toast
            this.showToast(errorMsg, 'error');
            
            // Try to find and highlight the cell
            const rows = this.table.getRows();
            if (rows && rowId < rows.length) {
                const row = rows[rowId];
                if (row) {
                    const cell = row.getCell(column);
                    if (cell && cell.getElement()) {
                        const element = cell.getElement();
                        
                        // Add visual error indication
                        element.style.backgroundColor = "rgba(239, 68, 68, 0.2)"; // Light red
                        
                        // Track error in version history if collaborative mode
                        if (this.isCollaborative && this.isConnected && this.socket) {
                            this.socket.send(JSON.stringify({
                                type: "validation_error",
                                rowId: rowId,
                                column: column,
                                value: value,
                                expected_dtype: expected_dtype,
                                error: errorMsg
                            }));
                        }
                        
                        // Reset after a delay
                        setTimeout(() => {
                            element.style.backgroundColor = "";
                        }, 2000);
                    }
                }
            }
        },
        
        // Set up cell events for collaborative editing
        setupCellEvents() {
            // Listen for cell edit start events
            this.table.on("cellEditing", (cell) => {
                // Convert 1-based to 0-based row position
                const row = cell.getRow().getPosition() - 1;
                const column = cell.getColumn().getField();
                this.sendCellFocus(row, column);
            });
            
            // Listen for cell edit events
            this.table.on("cellEdited", (cell) => {
                // Convert 1-based to 0-based row position
                const row = cell.getRow().getPosition() - 1;
                const column = cell.getColumn().getField();
                const value = cell.getValue();
                const oldValue = cell.getOldValue();
                
                // Save value locally
                this.tableData = this.table.getData();
                
                // Send edit to server
                this.sendCellEdit(row, column, value);
            });
            
            // Listen for cell blur events
            this.table.on("cellEditCancelled", (cell) => {
                // Convert 1-based to 0-based row position
                const row = cell.getRow().getPosition() - 1;
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
            
            // Get the old value before sending the edit for versioning purposes
            let oldValue = "";
            try {
                const currentData = this.table.getData();
                if (currentData && currentData[row]) {
                    oldValue = currentData[row][column] || "";
                }
            } catch (e) {
                console.error("Error getting old value:", e);
            }
            
            this.socket.send(JSON.stringify({
                type: "cell_edit",
                rowId: row,
                column: column,
                value: value,
                oldValue: oldValue
            }));
        },
        
        // Optimized mouse tracking with throttling
        trackMouseMovement() {
            if (!this.isCollaborative) return;
            
            let lastX = 0, lastY = 0;
            let throttled = false;
            
            document.addEventListener('mousemove', (e) => {
                if (throttled || !this.isConnected || !this.socket) return;
                
                // Only update if cursor moved significantly
                if (Math.abs(e.clientX - lastX) > 5 || Math.abs(e.clientY - lastY) > 5) {
                    lastX = e.clientX;
                    lastY = e.clientY;
                    
                    // Find cell under cursor
                    this.tryCaptureTableCell(e.clientX, e.clientY);
                    
                    // Apply throttling
                    throttled = true;
                    setTimeout(() => { throttled = false; }, 50);
                }
            });
        },
        
        // Send cursor position - optimized to send less data
        sendCursorPosition(row, column) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            this.socket.send(JSON.stringify({
                type: "cursor_position",
                position: {row, column}
            }));
        },
        
        // Simplified method to send table structure updates
        sendTableUpdate(data) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            const columns = this.table.getColumns().map(col => ({
                field: col.getField(),
                title: col.getDefinition().title
            }));
            
            this.socket.send(JSON.stringify({
                type: "table_structure",
                columns: columns,
                rowCount: data.length
            }));
        },
        
        // Send column reordering information
        sendColumnReorder(columns) {
            if (!this.isCollaborative || !this.isConnected) return;
            
            this.socket.send(JSON.stringify({
                type: "column_reorder",
                columns: columns
            }));
        },
        
        // Simplified method to capture table cell under cursor
        tryCaptureTableCell(clientX, clientY) {
            try {
                const tableRect = document.getElementById("data-table").getBoundingClientRect();
                if (clientX >= tableRect.left && clientX <= tableRect.right &&
                    clientY >= tableRect.top && clientY <= tableRect.bottom) {
                    
                    // Find cell element directly under cursor
                    const element = document.elementFromPoint(clientX, clientY);
                    if (!element) return;
                    
                    const cell = element.closest('.tabulator-cell');
                    if (!cell) return;
                    
                    const field = cell.getAttribute('tabulator-field');
                    const row = cell.closest('.tabulator-row');
                    if (!field || !row) return;
                    
                    // Find row position by counting previous siblings
                    let rowPosition = 0;
                    let current = row;
                    while (current.previousElementSibling) {
                        current = current.previousElementSibling;
                        if (current.classList.contains('tabulator-row')) {
                            rowPosition++;
                        }
                    }
                    
                    // Send cursor position to server
                    this.sendCursorPosition(rowPosition, field);
                }
            } catch (e) {
                console.error("Error finding cell under cursor:", e);
            }
        },
        
        // Simplified method to highlight cell for user
        highlightCellForUser(userId, rowPosition, colField) {
            if (!this.collaborators[userId]) return;
            
            // Remove any existing cursor indicators for this user
            document.querySelectorAll(`.user-cursor[data-user-id="${userId}"]`).forEach(el => el.remove());
            
            // Get user info
            const userName = this.collaborators[userId].name || "User";
            const userColor = this.collaborators[userId].color || "#3b82f6";
            
            // Find cell element
            const cellElements = document.querySelectorAll(`.tabulator-cell[tabulator-field="${colField}"]`);
            if (!cellElements || cellElements.length <= rowPosition) return;
            
            const cellElement = cellElements[rowPosition];
            const rect = cellElement.getBoundingClientRect();
            
            // Create highlight element
            const highlightEl = document.createElement("div");
            highlightEl.className = "user-cursor";
            highlightEl.setAttribute("data-user-id", userId);
            highlightEl.style.position = "absolute";
            highlightEl.style.left = `${rect.left}px`;
            highlightEl.style.top = `${rect.top}px`;
            highlightEl.style.width = `${rect.width}px`;
            highlightEl.style.height = `${rect.height}px`;
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
            nameTag.style.whiteSpace = "nowrap";
            nameTag.style.transform = "translateX(-50%)";
            nameTag.style.userSelect = "none";
            
            highlightEl.appendChild(nameTag);
            document.body.appendChild(highlightEl);
            
            // Auto-remove after delay
            setTimeout(() => {
                if (highlightEl.parentNode) highlightEl.remove();
            }, 2000);
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
            
            // Create dismiss button for error toasts
            if (type === 'error') {
                toast.style.backgroundColor = "#ef4444";
                toast.style.color = "white";
                toast.style.padding = "10px 15px";
                toast.style.borderLeft = "4px solid #b91c1c";
                
                const dismissBtn = document.createElement('button');
                dismissBtn.textContent = '×';
                dismissBtn.style.marginLeft = '10px';
                dismissBtn.style.background = 'none';
                dismissBtn.style.border = 'none';
                dismissBtn.style.color = 'white';
                dismissBtn.style.fontSize = '18px';
                dismissBtn.style.cursor = 'pointer';
                dismissBtn.style.fontWeight = 'bold';
                dismissBtn.onclick = () => toast.remove();
                
                toast.appendChild(dismissBtn);
            }
            
            const container = document.getElementById('toast-container') || document.body;
            container.appendChild(toast);
            
            // Auto dismiss after a longer time for errors
            setTimeout(() => {
                if (toast.parentNode) toast.remove();
            }, type === 'error' ? 5000 : 2300);
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
            if (this.isCollaborative) {
                // First save the data to ensure no changes are lost
                const data = this.table.getData();
                try {
                    // Save data and create a final snapshot
                    await fetch('/save_and_continue', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({data, create_snapshot: true}),
                    });
                    
                    // Clean up version history resources
                    this.cleanupVersionHistory();
                    
                    // Count active collaborators (excluding self)
                    const activeCollaborators = Object.keys(this.collaborators).length;
                    
                    // In test mode, skip confirmations
                    if (activeCollaborators === 0) {
                        // No other collaborators are present, shut down the server
                        if (!this.isTestMode && !confirm('You are the only user connected. Do you want to close the editor and save your changes?')) return;
                        
                        // Create a final "shutdown" snapshot before closing
                        await fetch('/create_snapshot', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                manual: true,
                                user_id: this.userId,
                                user_name: this.userName,
                                event: 'shutdown'
                            }),
                        });
                        
                        const response = await fetch('/shutdown', { method: 'POST' });
                        if (response.ok) {
                            this.showToast('Editor closing, data saved...', 'success');
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
                    } else {
                        // Other collaborators are active, just leave the session
                        if (!this.isTestMode && !confirm(`There are ${activeCollaborators} other collaborator(s) working on this file. Do you want to save your changes and exit?`)) return;
                        
                        // Notify others we're leaving
                        if (this.socket && this.isConnected) {
                            this.socket.send(JSON.stringify({
                                type: "user_finished",
                                userId: this.userId
                            }));
                        }
                        
                        this.showToast('Changes saved. Your session has ended.', 'success');
                        
                        // Close the current tab/window
                        setTimeout(() => {
                            if (window.parent !== window) {
                                window.parent.document.querySelector('iframe').remove();
                            } else {
                                window.close();
                            }
                        }, 1000);
                    }
                } catch (e) {
                    console.error('Error during exit operation:', e);
                    this.showToast('Error saving data', 'error');
                }
            } else {
                // Original behavior for non-collaborative mode
                if (!this.isTestMode && !confirm('Are you sure you want to send the data back and close the editor connection?')) return;
                try {
                    await this.saveData();
                    const response = await fetch('/shutdown', { method: 'POST' });
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
            }
        },
        
        // Cancel changes and close the editor
        async cancelChanges() {
            if (!this.isTestMode && !confirm('Are you sure you want to discard all changes and close the editor?')) return;
            try {
                // If in collaborative mode, track this cancellation in version history
                if (this.isCollaborative && this.isConnected && this.socket) {
                    // Create a snapshot noting the cancellation
                    try {
                        await fetch('/create_snapshot', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                manual: true,
                                user_id: this.userId,
                                user_name: this.userName,
                                event: 'cancel_changes'
                            }),
                        });
                        
                        // Notify other users
                        this.socket.send(JSON.stringify({
                            type: "user_cancelled",
                            userId: this.userId,
                            userName: this.userName
                        }));
                        
                        // Clean up version history resources
                        this.cleanupVersionHistory();
                    } catch (e) {
                        console.error("Error creating cancel snapshot:", e);
                    }
                }
                
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
        },
        
        // Fix the updateAbsoluteCursor method
        updateAbsoluteCursor(userId, cursor) {
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
            nameTag.style.color = "white";
            nameTag.style.position = "absolute";
            nameTag.style.top = "-20px";
            nameTag.style.left = "0";
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

        // ------ Version History Methods ------
        
        // Toggle version history sidebar
        toggleVersionHistory() {
            this.isVersionHistorySidebarOpen = !this.isVersionHistorySidebarOpen;
            
            if (this.isVersionHistorySidebarOpen && this.versionSnapshots.length === 0) {
                // Load version history when opening the sidebar
                this.loadVersionHistory();
                
                // Start auto-refresh when sidebar is open
                this.startVersionHistoryAutoRefresh();
            } else if (!this.isVersionHistorySidebarOpen) {
                // Stop auto-refresh when sidebar is closed
                this.stopVersionHistoryAutoRefresh();
            }
        },
        
        // Start auto-refresh for version history
        startVersionHistoryAutoRefresh() {
            // Clear any existing interval
            this.stopVersionHistoryAutoRefresh();
            
            // Set up new interval - refresh every 10 seconds
            this.versionHistoryInterval = setInterval(() => {
                if (this.isVersionHistorySidebarOpen) {
                    this.loadVersionHistory();
                }
            }, 10000);
        },
        
        // Stop auto-refresh for version history
        stopVersionHistoryAutoRefresh() {
            if (this.versionHistoryInterval) {
                clearInterval(this.versionHistoryInterval);
                this.versionHistoryInterval = null;
            }
        },
        
        // Load version history from the server
        async loadVersionHistory() {
            try {
                const response = await fetch('/version_history');
                if (!response.ok) {
                    throw new Error(`Failed to load version history: ${response.statusText}`);
                }
                
                const data = await response.json();
                if (data.error) {
                    console.error("Version history error:", data.error);
                    return;
                }
                
                this.versionSnapshots = data.snapshots || [];
                this.versionChanges = data.changes || [];
                
                // Sort snapshots by timestamp in descending order
                this.versionSnapshots.sort((a, b) => b.timestamp - a.timestamp);
                
            } catch (error) {
                console.error("Error loading version history:", error);
                this.showToast("Error loading version history", "error");
            }
        },
        
        // Format timestamp for display
        formatTimestamp(timestamp) {
            const date = new Date(timestamp * 1000);
            return date.toLocaleString();
        },
        
        // Format time for display (without date)
        formatTime(timestamp) {
            const date = new Date(timestamp * 1000);
            return date.toLocaleTimeString();
        },
        
        // Toggle snapshot expansion
        toggleSnapshot(snapshotId) {
            if (this.expandedSnapshots.includes(snapshotId)) {
                this.expandedSnapshots = this.expandedSnapshots.filter(id => id !== snapshotId);
            } else {
                this.expandedSnapshots.push(snapshotId);
            }
        },
        
        // Get changes for a specific snapshot
        getSnapshotChanges(snapshotId) {
            const snapshot = this.versionSnapshots.find(s => s.id === snapshotId);
            if (!snapshot) return [];
            
            return this.versionChanges.filter(change => 
                change.timestamp >= snapshot.interval_start && 
                change.timestamp < snapshot.interval_end
            ).sort((a, b) => a.timestamp - b.timestamp);
        },
        
        // Show context menu for snapshot
        showSnapshotContextMenu(event, snapshotId) {
            event.preventDefault();
            
            // Hide any other context menus
            this.hideContextMenus();
            
            // Show this context menu
            this.snapshotContextMenu = {
                visible: true,
                x: event.clientX,
                y: event.clientY,
                snapshotId: snapshotId
            };
        },
        
        // Show context menu for change
        showChangeContextMenu(event, changeId) {
            event.preventDefault();
            
            // Hide any other context menus
            this.hideContextMenus();
            
            // Show this context menu
            this.changeContextMenu = {
                visible: true,
                x: event.clientX,
                y: event.clientY,
                changeId: changeId
            };
        },
        
        // Hide all context menus
        hideContextMenus() {
            this.snapshotContextMenu.visible = false;
            this.changeContextMenu.visible = false;
        },
        
        // Restore to a specific version
        async restoreVersion(snapshotId) {
            if (!snapshotId) return;
            
            try {
                const response = await fetch('/restore_version', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ snapshot_id: snapshotId })
                });
                
                if (!response.ok) {
                    throw new Error(`Failed to restore version: ${response.statusText}`);
                }
                
                const result = await response.json();
                if (result.error) {
                    throw new Error(result.error);
                }
                
                // Reload data after restore
                await this.loadData().then(data => {
                    if (data && data.length > 0) {
                        this.table.setData(data);
                        this.tableData = data;
                    }
                });
                
                this.showToast("Restored to previous version", "success");
                
                // Hide the sidebar and context menus
                this.isVersionHistorySidebarOpen = false;
                this.hideContextMenus();
                
                // Notify others in collaborative mode
                if (this.isCollaborative && this.isConnected && this.socket) {
                    this.socket.send(JSON.stringify({
                        type: "version_restored",
                        userId: this.userId,
                        snapshotId: snapshotId
                    }));
                }
                
            } catch (error) {
                console.error("Error restoring version:", error);
                this.showToast("Error restoring version: " + error.message, "error");
            }
        },
        
        // Revert a specific change
        async revertChange(changeId) {
            if (!changeId) return;
            
            try {
                const response = await fetch('/restore_version', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ change_id: changeId })
                });
                
                if (!response.ok) {
                    throw new Error(`Failed to revert change: ${response.statusText}`);
                }
                
                const result = await response.json();
                if (result.error) {
                    throw new Error(result.error);
                }
                
                // Reload data after revert
                await this.loadData().then(data => {
                    if (data && data.length > 0) {
                        this.table.setData(data);
                        this.tableData = data;
                    }
                });
                
                this.showToast("Change reverted successfully", "success");
                this.hideContextMenus();
                
                // Notify others in collaborative mode
                if (this.isCollaborative && this.isConnected && this.socket) {
                    this.socket.send(JSON.stringify({
                        type: "version_restored",
                        userId: this.userId,
                        changeId: changeId
                    }));
                }
                
            } catch (error) {
                console.error("Error reverting change:", error);
                this.showToast("Error reverting change: " + error.message, "error");
            }
        },
        
        // Create a manual snapshot of the current data
        async createManualSnapshot() {
            if (!this.isCollaborative) return;
            
            try {
                const response = await fetch('/create_snapshot', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        manual: true,
                        user_id: this.userId,
                        user_name: this.userName
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`Failed to create snapshot: ${response.statusText}`);
                }
                
                const result = await response.json();
                if (result.error) {
                    throw new Error(result.error);
                }
                
                this.showToast("Version snapshot created successfully", "success");
                
                // Refresh version history if sidebar is open
                if (this.isVersionHistorySidebarOpen) {
                    this.loadVersionHistory();
                }
                
            } catch (error) {
                console.error("Error creating snapshot:", error);
                this.showToast("Error creating snapshot: " + error.message, "error");
            }
        },
        
        // Clean up version history resources
        cleanupVersionHistory() {
            // Stop auto-refresh interval
            this.stopVersionHistoryAutoRefresh();
            
            // Close any context menus
            this.hideContextMenus();
            
            // Clear any expanded snapshots
            this.expandedSnapshots = [];
        },
    };
}

function setupTooltip() {
    const tooltip = document.getElementById('column-rename-tooltip');
    const dismissButton = document.getElementById('dismiss-tooltip');
    
    // Show tooltip after a slight delay
    setTimeout(() => {
        if (tooltip) tooltip.style.display = 'block';
    }, 1000);
    
    // Dismiss with button click
    if (dismissButton) {
        dismissButton.addEventListener('click', () => {
            hideTooltip();
        });
    }
    
    // Dismiss with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && tooltip && tooltip.style.display !== 'none') {
            hideTooltip();
        }
    });
    
    function hideTooltip() {
        if (tooltip) {
            tooltip.style.opacity = '0';
            tooltip.style.transform = 'translateY(10px)';
            setTimeout(() => {
                tooltip.style.display = 'none';
            }, 300);
        }
    }
}