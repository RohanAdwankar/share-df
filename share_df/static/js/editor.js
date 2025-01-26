let table;
let columnCount = 0;

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
        hideLoading();
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