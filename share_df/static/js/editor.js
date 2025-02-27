let table;
let columnCount = 0;
let socket;
let userId;
let collaborators = {};
let cellEditors = {};
let userName = "User " + Math.floor(Math.random() * 1000);
let userColor = getRandomColor();
let isConnected = false;

function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

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
    }, false);
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

            const updatedData = allData.map(row => {
                const newRow = {...row};
                newRow[newValue] = row[oldField];
                delete newRow[oldField];
                return newRow;
            });

            table.setColumns(newColumnDefinitions);
            table.setData(updatedData);
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
}

async function shutdownServer() {
    if (confirm('Are you sure you want to send the data back and close the editor connection?')) {
        try {
            await saveData();
            const response = await fetch('/shutdown', {method: 'POST'});
            if (response.ok) {
                showToast('Server shutting down...', 'success');
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
            showToast('Error shutting down server', 'error');
        }
    }
}

async function loadData() {
    try {
        showLoading();
        const response = await fetch('/data');
        const data = await response.json();
        if (!data || data.length === 0) {
            hideLoading();
            showToast('No data available', 'error');
            return [];
        }
        document.getElementById('loading-text').textContent = `Preparing ${data.length.toLocaleString()} rows...`;
        return data;
    } catch (e) {
        console.error('Error loading data:', e);
        showToast('Error loading data', 'error');
        hideLoading();
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

function getRandomColor() {
    const colors = [
        "#3b82f6", "#ef4444", "#10b981", "#f59e0b", 
        "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"
    ];
    return colors[Math.floor(Math.random() * colors.length)];
}

function setupWebSocket() {
    if (!isCollaborative) return;
    
    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    const wsUrl = `${protocol}${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = function(e) {
        console.log("WebSocket connection established");
        isConnected = true;
        
        // Ask for user name when first connecting
        const name = prompt("Enter your name for collaboration:", userName) || userName;
        userName = name;
        
        // Send user info to server
        socket.send(JSON.stringify({
            type: "update_user",
            name: userName,
            color: userColor
        }));
    };
    
    socket.onmessage = function(event) {
        handleWebSocketMessage(JSON.parse(event.data));
    };
    
    socket.onclose = function(event) {
        console.log("WebSocket connection closed");
        isConnected = false;
        
        if (event.wasClean) {
            showToast(`Connection closed: ${event.reason}`, 'error');
        } else {
            // Connection died
            showToast("Connection lost. Please refresh the page.", 'error');
        }
    };
    
    socket.onerror = function(error) {
        console.error("WebSocket error:", error);
        showToast("WebSocket error occurred", 'error');
    };
}

function handleWebSocketMessage(message) {
    console.log("Received message:", message);
    
    switch (message.type) {
        case "init":
            // Initialize with server-provided data
            userId = message.userId;
            
            // Add existing collaborators
            message.collaborators.forEach(user => {
                if (user.id !== userId) {
                    collaborators[user.id] = user;
                }
            });
            
            updateCollaboratorsList();
            break;
            
        case "user_joined":
            showToast(`${message.name || "A new user"} joined the session`, 'success');
            // Rest of handling remains the same
            break;
            
        case "user_update":
            // Update or add collaborator
            if (message.user && message.user.id !== userId) {
                collaborators[message.user.id] = message.user;
                updateCollaboratorsList();
                
                // Only show toast for first update from a user
                if (!document.querySelector(`.collaborator-badge[data-user-id="${message.user.id}"]`)) {
                    showToast(`${message.user.name} joined the session`, 'success');
                }
            }
            break;
            
        case "user_left":
            // Remove collaborator
            if (message.userId && collaborators[message.userId]) {
                const userName = collaborators[message.userId].name;
                delete collaborators[message.userId];
                updateCollaboratorsList();
                
                // Remove any cursors for this user
                document.querySelectorAll(`.user-cursor[data-user-id="${message.userId}"]`).forEach(el => el.remove());
                
                showToast(`${userName} left the session`, 'error');
            }
            break;
            
        case "cell_focus":
            // Another user is focusing on a cell
            if (message.userId !== userId) {
                const cellId = message.cellId;
                const [rowId, colField] = cellId.split("-");
                
                const cell = table.getCell(rowId, colField);
                if (cell && cell.getElement()) {
                    const userName = collaborators[message.userId]?.name || "User";
                    const userColor = collaborators[message.userId]?.color || "#3b82f6";
                    
                    // Mark the cell as being edited
                    cell.getElement().classList.add("cell-being-edited");
                    cell.getElement().style.boxShadow = `0 0 0 2px ${userColor} inset`;
                    
                    // Add editor name
                    const nameTag = document.createElement("div");
                    nameTag.className = "editor-name";
                    nameTag.textContent = userName;
                    nameTag.style.backgroundColor = userColor;
                    nameTag.style.color = "#ffffff"; // Ensure text is visible
                    cell.getElement().appendChild(nameTag);
                }
            }
            break;
            
        case "cell_blur":
            // User stopped editing a cell
            if (message.userId !== userId) {
                const cellId = message.cellId;
                const [rowId, colField] = cellId.split("-");
                
                const cell = table.getCell(rowId, colField);
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
            // Another user edited a cell - update immediately
            if (message.userId !== userId) {
                const rowId = message.rowId;
                const column = message.column;
                const value = message.value;
                
                // Find the cell and update it
                try {
                    const cell = table.getCell(rowId, column);
                    if (cell) {
                        cell.setValue(value, false); // Silent update (no events)
                    } else {
                        // If cell not found, update data model
                        let rowData = table.getRow(rowId)?.getData() || {};
                        rowData[column] = value;
                        table.updateData([rowData]);
                    }
                } catch (e) {
                    console.error("Error updating cell:", e);
                }
            }
            break;
            
        case "cursor_move":
            // Another user moved their cursor
            if (message.userId !== userId && message.cursor) {
                updateCursor(message.userId, message.cursor);
            }
            break;
    }
}

function updateCursor(userId, cursor) {
    if (!collaborators[userId]) return;
    
    // Remove old cursor
    document.querySelectorAll(`.user-cursor[data-user-id="${userId}"]`).forEach(el => el.remove());
    
    // If cursor position is invalid, don't show it
    if (cursor.row < 0 || cursor.col < 0) return;
    
    // Create cursor element
    const cursorElement = document.createElement("div");
    cursorElement.className = "user-cursor";
    cursorElement.setAttribute("data-user-id", userId);
    cursorElement.style.backgroundColor = collaborators[userId].color;
    
    // Add name tag to cursor
    const nameTag = document.createElement("div");
    nameTag.className = "cursor-name";
    nameTag.textContent = collaborators[userId].name;
    nameTag.style.backgroundColor = collaborators[userId].color;
    cursorElement.appendChild(nameTag);
    
    // Calculate position based on cursor data
    // This is a simplistic approach - real implementation would need more complex positioning
    const tableRect = document.getElementById("data-table").getBoundingClientRect();
    cursorElement.style.left = `${cursor.x}px`;
    cursorElement.style.top = `${cursor.y}px`;
    
    // Add to DOM
    document.body.appendChild(cursorElement);
}

function updateCollaboratorsList() {
    if (!isCollaborative) return;
    
    const container = document.getElementById("collaborators-list");
    const containerParent = document.getElementById("collaborators-container");
    if (!container || !containerParent) return;
    
    container.innerHTML = "";
    
    const collaboratorCount = Object.keys(collaborators).length;
    
    // Only show the collaborators section if there are actually people
    if (collaboratorCount === 0) {
        containerParent.style.display = "none";
        return;
    } else {
        containerParent.style.display = "flex";
    }
    
    Object.values(collaborators).forEach(user => {
        const badge = document.createElement("div");
        badge.className = "collaborator-badge";
        badge.setAttribute("data-user-id", user.id);
        badge.style.backgroundColor = `${user.color}20`; // 20% opacity
        badge.style.borderColor = user.color;
        badge.style.color = user.color; // Text color matches user color
        
        const dot = document.createElement("div");
        dot.className = "collaborator-dot";
        dot.style.backgroundColor = user.color;
        badge.appendChild(dot);
        
        badge.appendChild(document.createTextNode(user.name));
        container.appendChild(badge);
    });
}

function sendCellFocus(row, column) {
    if (!isCollaborative || !isConnected) return;
    
    const cellId = `${row}-${column}`;
    socket.send(JSON.stringify({
        type: "cell_focus",
        cellId: cellId
    }));
}

function sendCellBlur(row, column) {
    if (!isCollaborative || !isConnected) return;
    
    const cellId = `${row}-${column}`;
    socket.send(JSON.stringify({
        type: "cell_blur",
        cellId: cellId
    }));
}

function sendCellEdit(row, column, value) {
    if (!isCollaborative || !isConnected) return;
    
    socket.send(JSON.stringify({
        type: "cell_edit",
        rowId: row,
        column: column,
        value: value
    }));
}

function trackMouseMovement() {
    if (!isCollaborative || !isConnected) return;
    
    let lastX = 0, lastY = 0;
    let throttled = false;
    
    document.addEventListener('mousemove', function(e) {
        if (throttled) return;
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
                socket.send(JSON.stringify({
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
            },
            reactiveData: true, // Make data reactive
        });
        
        // Hide loading overlay
        hideLoading();
        
        // Initialize WebSocket connection for collaboration
        if (isCollaborative) {
            setupWebSocket();
            trackMouseMovement();
            setupCellEvents();
            
            // Hide save button in collaborative mode
            document.querySelector('.save-button').style.display = 'none';
        }
    } catch (e) {
        console.error('Error initializing table:', e);
        showToast('Error initializing table', 'error');
        hideLoading();
    }
}

async function cancelChanges() {
    if (confirm('Are you sure you want to discard all changes and close the editor?')) {
        try {
            const response = await fetch('/cancel', {
                method: 'POST'
            });
            
            if (response.ok) {
                showToast('Discarding changes...', 'success');
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
            showToast('Error canceling changes', 'error');
        }
    }
}

document.addEventListener('DOMContentLoaded', initializeTable);

// Update cell focus and editing functionality
function setupCellEvents() {
    if (!isCollaborative) return;
    
    // Listen for cell focus events
    table.on("cellClick", function(e, cell) {
        const row = cell.getRow().getData().id || cell.getRow().getPosition();
        const column = cell.getColumn().getField();
        sendCellFocus(row, column);
    });
    
    // Listen for cell edit events
    table.on("cellEdited", function(cell) {
        const row = cell.getRow().getData().id || cell.getRow().getPosition();
        const column = cell.getColumn().getField();
        const value = cell.getValue();
        
        // Send edit to server immediately
        sendCellEdit(row, column, value);
    });
    
    // Listen for cell blur events
    table.on("cellEditCancelled", function(cell) {
        const row = cell.getRow().getData().id || cell.getRow().getPosition();
        const column = cell.getColumn().getField();
        sendCellBlur(row, column);
    });
}