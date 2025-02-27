/**
 * Debugging utilities for Tabulator cells and rows
 */

function debugTable(table, containerId = 'data-table') {
    if (!table) {
        console.error("Table object not provided for debugging");
        return;
    }
    
    // Create debug button
    const debugButton = document.createElement('button');
    debugButton.textContent = 'Debug Table';
    debugButton.style.position = 'fixed';
    debugButton.style.bottom = '10px';
    debugButton.style.left = '10px';
    debugButton.style.zIndex = '9999';
    debugButton.style.padding = '5px 10px';
    debugButton.style.backgroundColor = '#3b82f6';
    debugButton.style.color = 'white';
    debugButton.style.border = 'none';
    debugButton.style.borderRadius = '4px';
    debugButton.style.cursor = 'pointer';
    
    // Add click event
    debugButton.addEventListener('click', () => {
        const info = collectTableInfo(table);
        showTableInfo(info);
    });
    
    document.body.appendChild(debugButton);
    
    // Monitor for table errors
    monitorTableEvents(table, containerId);
}

function collectTableInfo(table) {
    const info = {
        rowCount: 0,
        columnCount: 0,
        columns: [],
        sampleCells: [],
        errors: []
    };
    
    try {
        const rows = table.getRows();
        info.rowCount = rows.length;
        
        const columns = table.getColumns();
        info.columnCount = columns.length;
        
        info.columns = columns.map(col => ({
            field: col.getField(),
            title: col.getDefinition().title,
            visible: col.isVisible()
        }));
        
        // Sample some cells for debugging
        if (rows.length > 0 && columns.length > 0) {
            // Get first row, first column
            try {
                const firstCell = rows[0].getCell(columns[0].getField());
                info.sampleCells.push({
                    row: 0,
                    column: columns[0].getField(),
                    value: firstCell.getValue(),
                    element: firstCell.getElement() ? true : false
                });
            } catch (e) {
                info.errors.push(`Error accessing first cell: ${e.message}`);
            }
            
            // Get middle row, middle column if available
            if (rows.length > 2 && columns.length > 2) {
                try {
                    const midRow = Math.floor(rows.length / 2);
                    const midCol = columns[Math.floor(columns.length / 2)].getField();
                    const midCell = rows[midRow].getCell(midCol);
                    info.sampleCells.push({
                        row: midRow,
                        column: midCol,
                        value: midCell.getValue(),
                        element: midCell.getElement() ? true : false
                    });
                } catch (e) {
                    info.errors.push(`Error accessing middle cell: ${e.message}`);
                }
            }
        }
    } catch (e) {
        info.errors.push(`Error collecting table info: ${e.message}`);
    }
    
    return info;
}

function showTableInfo(info) {
    console.group('Table Debug Information');
    console.log('Row Count:', info.rowCount);
    console.log('Column Count:', info.columnCount);
    console.log('Columns:', info.columns);
    console.log('Sample Cells:', info.sampleCells);
    
    if (info.errors.length > 0) {
        console.error('Errors:', info.errors);
    }
    console.groupEnd();
    
    // Also show in a formatted panel
    const debugPanel = document.createElement('div');
    debugPanel.style.position = 'fixed';
    debugPanel.style.top = '50%';
    debugPanel.style.left = '50%';
    debugPanel.style.transform = 'translate(-50%, -50%)';
    debugPanel.style.padding = '20px';
    debugPanel.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
    debugPanel.style.color = '#fff';
    debugPanel.style.borderRadius = '8px';
    debugPanel.style.maxWidth = '80%';
    debugPanel.style.maxHeight = '80%';
    debugPanel.style.overflow = 'auto';
    debugPanel.style.zIndex = '10000';
    debugPanel.style.fontFamily = 'monospace';
    
    let content = `
        <h3 style="margin-top:0">Table Debug Info</h3>
        <p><strong>Row Count:</strong> ${info.rowCount}</p>
        <p><strong>Column Count:</strong> ${info.columnCount}</p>
        <h4>Columns:</h4>
        <ul>
            ${info.columns.map(col => 
                `<li>${col.title} (${col.field}) - ${col.visible ? 'Visible' : 'Hidden'}</li>`
            ).join('')}
        </ul>
        <h4>Sample Cells:</h4>
        <ul>
            ${info.sampleCells.map(cell => 
                `<li>Row ${cell.row}, Column ${cell.column}: ${cell.value} 
                 (Element: ${cell.element ? 'Yes' : 'No'})</li>`
            ).join('')}
        </ul>
    `;
    
    if (info.errors.length > 0) {
        content += `
            <h4 style="color:#ef4444">Errors:</h4>
            <ul>
                ${info.errors.map(err => `<li>${err}</li>`).join('')}
            </ul>
        `;
    }
    
    content += `
        <button id="close-debug-panel" style="
            background-color: #3b82f6;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            margin-top: 10px;
            cursor: pointer;
        ">Close</button>
    `;
    
    debugPanel.innerHTML = content;
    document.body.appendChild(debugPanel);
    
    document.getElementById('close-debug-panel').addEventListener('click', () => {
        debugPanel.remove();
    });
}

function monitorTableEvents(table, containerId) {
    // Monitor table events for errors
    const originalConsoleError = console.error;
    console.error = function() {
        // Call the original console.error
        originalConsoleError.apply(console, arguments);
        
        // Check if this is a Tabulator-related error
        const errorText = Array.from(arguments).join(' ');
        if (errorText.includes('tabulator') || 
            errorText.includes('cell') || 
            errorText.includes('row') || 
            errorText.includes('column')) {
            
            // Log table state when errors occur
            const info = collectTableInfo(table);
            console.warn('Table state at time of error:', info);
        }
    };
    
    // Create a MutationObserver to watch for DOM changes
    const tableElement = document.getElementById(containerId);
    if (tableElement) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'childList' && mutation.removedNodes.length > 0) {
                    console.log('DOM nodes removed from table:', mutation.removedNodes);
                }
            });
        });
        
        observer.observe(tableElement, { 
            childList: true,
            subtree: true
        });
    }
}

// Auto-initialize when the debug flag is present
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (window.location.search.includes('debug=table')) {
            // Wait for Tabulator to initialize
            setTimeout(() => {
                if (window.editorApp && window.editorApp.table) {
                    debugTable(window.editorApp.table);
                }
            }, 2000);
        }
    });
}

// Export for manual use
window.debugTable = debugTable;
