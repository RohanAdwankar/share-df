/**
 * Debug utilities for collaborative editing
 * Add this script to your template for troubleshooting cell position issues
 */

// Global debug state
window.collabDebug = {
    enabled: false,
    showCellIndices: false,
    showRowIds: false,
    traceMessages: false
};

// Initialize debug mode
function initDebugMode() {
    // Add debug button
    const button = document.createElement('button');
    button.id = 'collab-debug-button';
    button.textContent = 'Debug Mode';
    button.style.position = 'fixed';
    button.style.bottom = '10px';
    button.style.right = '10px';
    button.style.padding = '8px 12px';
    button.style.backgroundColor = '#3b82f6';
    button.style.color = 'white';
    button.style.border = 'none';
    button.style.borderRadius = '4px';
    button.style.zIndex = '9999';
    button.style.fontWeight = 'bold';
    button.style.cursor = 'pointer';
    
    // Toggle debug mode on click
    button.addEventListener('click', () => {
        window.collabDebug.enabled = !window.collabDebug.enabled;
        button.style.backgroundColor = window.collabDebug.enabled ? '#ef4444' : '#3b82f6';
        button.textContent = window.collabDebug.enabled ? 'Debug ON' : 'Debug Mode';
        
        if (window.collabDebug.enabled) {
            showDebugPanel();
            highlightCells();
        } else {
            const panel = document.getElementById('collab-debug-panel');
            if (panel) panel.remove();
            
            // Remove cell highlights
            document.querySelectorAll('.cell-debug-marker').forEach(el => el.remove());
        }
    });
    
    document.body.appendChild(button);
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', e => {
        // Ctrl+Alt+D to toggle debug mode
        if (e.ctrlKey && e.altKey && e.key === 'd') {
            window.collabDebug.enabled = !window.collabDebug.enabled;
            button.click(); // Simulate click to update UI
        }
        
        // Ctrl+Alt+C to toggle cell indices
        if (e.ctrlKey && e.altKey && e.key === 'c') {
            window.collabDebug.showCellIndices = !window.collabDebug.showCellIndices;
            highlightCells();
        }
    });
}

// Show debug panel
function showDebugPanel() {
    // Remove existing panel if any
    const existingPanel = document.getElementById('collab-debug-panel');
    if (existingPanel) existingPanel.remove();
    
    // Create panel
    const panel = document.createElement('div');
    panel.id = 'collab-debug-panel';
    panel.style.position = 'fixed';
    panel.style.top = '10px';
    panel.style.right = '10px';
    panel.style.width = '300px';
    panel.style.padding = '15px';
    panel.style.backgroundColor = 'rgba(0,0,0,0.85)';
    panel.style.color = 'white';
    panel.style.borderRadius = '5px';
    panel.style.zIndex = '9998';
    panel.style.fontSize = '14px';
    panel.style.fontFamily = 'monospace';
    panel.style.backdropFilter = 'blur(5px)';
    
    // Add options
    panel.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
            <b>Collaborative Debug 🐞</b>
            <span id="debug-close-btn" style="cursor:pointer;">✖</span>
        </div>
        <div style="margin-bottom:8px;">
            <label>
                <input type="checkbox" id="debug-cell-indices" ${window.collabDebug.showCellIndices ? 'checked' : ''}>
                Show Cell Indices
            </label>
        </div>
        <div style="margin-bottom:8px;">
            <label>
                <input type="checkbox" id="debug-row-ids" ${window.collabDebug.showRowIds ? 'checked' : ''}>
                Show Row IDs
            </label>
        </div>
        <div style="margin-bottom:8px;">
            <label>
                <input type="checkbox" id="debug-trace-messages" ${window.collabDebug.traceMessages ? 'checked' : ''}>
                Trace WS Messages
            </label>
        </div>
        <div style="margin-top:15px;">
            <button id="debug-analyze-button" style="width:100%; padding:5px; background:#3b82f6; color:white; border:none; border-radius:3px; cursor:pointer;">
                Analyze Table Structure
            </button>
        </div>
    `;
    
    document.body.appendChild(panel);
    
    // Add event handlers
    document.getElementById('debug-close-btn').addEventListener('click', () => {
        panel.remove();
    });
    
    document.getElementById('debug-cell-indices').addEventListener('change', e => {
        window.collabDebug.showCellIndices = e.target.checked;
        highlightCells();
    });
    
    document.getElementById('debug-row-ids').addEventListener('change', e => {
        window.collabDebug.showRowIds = e.target.checked;
        highlightCells();
    });
    
    document.getElementById('debug-trace-messages').addEventListener('change', e => {
        window.collabDebug.traceMessages = e.target.checked;
    });
    
    document.getElementById('debug-analyze-button').addEventListener('click', analyzeTableStructure);
}

// Highlight cells with position information
function highlightCells() {
    // Remove existing highlights
    document.querySelectorAll('.cell-debug-marker').forEach(el => el.remove());
    
    if (!window.collabDebug.enabled) return;
    if (!window.collabDebug.showCellIndices && !window.collabDebug.showRowIds) return;
    
    const cells = document.querySelectorAll('.tabulator-cell');
    
    cells.forEach((cell, index) => {
        // Get cell info
        const field = cell.getAttribute('tabulator-field');
        const row = cell.closest('.tabulator-row');
        let rowPos = 0;
        let current = row;
        
        // Calculate row position by counting previous siblings
        while (current.previousElementSibling) {
            current = current.previousElementSibling;
            if (current.classList.contains('tabulator-row')) {
                rowPos++;
            }
        }
        
        // Get row ID from data if available
        let rowId = '';
        if (window.editorApp && window.editorApp.table) {
            try {
                const tableRows = window.editorApp.table.getRows();
                if (tableRows.length > rowPos) {
                    rowId = tableRows[rowPos].getData()._row_id || '';
                }
            } catch (e) {
                console.error('Error getting row ID:', e);
            }
        }
        
        // Create marker
        const marker = document.createElement('div');
        marker.className = 'cell-debug-marker';
        marker.style.position = 'absolute';
        marker.style.top = '1px';
        marker.style.right = '1px';
        marker.style.fontSize = '9px';
        marker.style.padding = '1px 3px';
        marker.style.backgroundColor = 'rgba(239, 68, 68, 0.7)';
        marker.style.color = 'white';
        marker.style.borderRadius = '2px';
        marker.style.pointerEvents = 'none';
        marker.style.zIndex = '1000';
        
        // Set content based on options
        if (window.collabDebug.showCellIndices && window.collabDebug.showRowIds) {
            marker.textContent = `${rowPos}:${field} (${rowId.substr(-5)})`;
        } else if (window.collabDebug.showCellIndices) {
            marker.textContent = `${rowPos}:${field}`;
        } else if (window.collabDebug.showRowIds) {
            marker.textContent = rowId.substr(-8);
        }
        
        // Make sure cell has position relative
        if (window.getComputedStyle(cell).position === 'static') {
            cell.style.position = 'relative';
        }
        
        cell.appendChild(marker);
    });
}

// Analyze table structure
function analyzeTableStructure() {
    if (!window.editorApp || !window.editorApp.table) {
        console.error('Editor app or table not found');
        return;
    }
    
    console.group('Table Structure Analysis');
    
    // Get basic table info
    const rows = window.editorApp.table.getRows();
    const columns = window.editorApp.table.getColumns();
    
    console.log(`Table has ${rows.length} rows and ${columns.length} columns`);
    
    // Check row IDs
    const rowIds = rows.map(row => row.getData()._row_id || 'missing');
    const uniqueIds = new Set(rowIds);
    
    console.log(`Unique row IDs: ${uniqueIds.size} of ${rowIds.length}`);
    if (uniqueIds.size !== rowIds.length) {
        console.warn('Duplicate row IDs detected!');
        
        // Find duplicates
        const idCounts = {};
        rowIds.forEach(id => {
            idCounts[id] = (idCounts[id] || 0) + 1;
        });
        
        const duplicates = Object.entries(idCounts)
            .filter(([id, count]) => count > 1)
            .map(([id, count]) => `${id} (${count}x)`);
            
        console.warn('Duplicates:', duplicates);
    }
    
    // Check DOM vs Data model consistency
    const domRows = document.querySelectorAll('.tabulator-row:not(.tabulator-calcs)').length;
    if (domRows !== rows.length) {
        console.warn(`DOM row count (${domRows}) doesn't match data model row count (${rows.length})`);
    }
    
    console.log('Sample rows:', rows.slice(0, 3).map(row => ({
        position: row.getPosition(),
        id: row.getData()._row_id
    })));
    
    console.groupEnd();
    
    // Show toast with results
    const toast = document.createElement('div');
    toast.className = 'debug-toast';
    toast.style.position = 'fixed';
    toast.style.bottom = '50px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.padding = '10px 15px';
    toast.style.backgroundColor = 'rgba(0,0,0,0.85)';
    toast.style.color = 'white';
    toast.style.borderRadius = '5px';
    toast.style.zIndex = '9999';
    toast.style.backdropFilter = 'blur(5px)';
    toast.innerHTML = `
        <div><b>Table Analysis:</b></div>
        <div>Rows: ${rows.length}</div>
        <div>Columns: ${columns.length}</div>
        <div>Row IDs: ${uniqueIds.size === rowIds.length ? '✓ All unique' : '⚠ Has duplicates'}</div>
        <div>DOM Consistency: ${domRows === rows.length ? '✓ Good' : '⚠ Mismatch'}</div>
        <div style="margin-top:5px;font-size:12px;opacity:0.8;">See console for details</div>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 5000);
}

// Initialize when the document is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDebugMode);
} else {
    initDebugMode();
}

// Monitor for WebSocket messages if debug mode is enabled
const originalWebSocketSend = WebSocket.prototype.send;
WebSocket.prototype.send = function(data) {
    // Call the original method
    originalWebSocketSend.call(this, data);
    
    // Log outgoing messages if debug mode is enabled
    if (window.collabDebug && window.collabDebug.traceMessages) {
        try {
            const message = JSON.parse(data);
            console.log('%c⬆ WS OUT:', 'color: #10b981; font-weight: bold;', message);
        } catch (e) {
            // Not JSON or other error
            console.log('%c⬆ WS OUT:', 'color: #10b981; font-weight: bold;', data);
        }
    }
};

// Add event handler to update position markers when table updates
function setupTableObserver() {
    const observer = new MutationObserver(mutations => {
        for (const mutation of mutations) {
            if (mutation.type === 'childList' && 
               (mutation.target.classList.contains('tabulator-tableHolder') || 
                mutation.target.classList.contains('tabulator-table'))) {
                if (window.collabDebug.enabled && 
                   (window.collabDebug.showCellIndices || window.collabDebug.showRowIds)) {
                    setTimeout(highlightCells, 100);
                    break;
                }
            }
        }
    });
    
    // Start observing the table container
    const tableElement = document.getElementById('data-table');
    if (tableElement) {
        observer.observe(tableElement, {
            childList: true,
            subtree: true
        });
    }
}

// Set up observer when the table is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(setupTableObserver, 1000);
    });
} else {
    setTimeout(setupTableObserver, 1000);
}
