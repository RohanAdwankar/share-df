/**
 * Helper utility for diagnosing cell position issues
 */

// Add this to the end of editor-alpine.js or include as a separate script
window.debugCellPositions = function() {
    // Get all table cells
    const cells = document.querySelectorAll('.tabulator-cell');
    console.group('Cell Position Diagnostics');
    
    console.log(`Found ${cells.length} cells in the table`);
    
    // Analyze first few rows
    const rows = {};
    cells.forEach((cell, index) => {
        const field = cell.getAttribute('tabulator-field');
        const rowEl = cell.closest('.tabulator-row');
        const rowPosition = Array.from(rowEl.parentNode.children).indexOf(rowEl);
        
        if (!rows[rowPosition]) {
            rows[rowPosition] = [];
        }
        
        rows[rowPosition].push({
            field,
            index,
            rect: cell.getBoundingClientRect()
        });
    });
    
    // Log the first 3 rows for diagnosis
    for (let i = 0; i < 3; i++) {
        if (rows[i]) {
            console.log(`Row ${i}: ${rows[i].length} cells`);
            rows[i].forEach(cell => {
                console.log(`  Field: ${cell.field}, Index: ${cell.index}, Position: ${cell.rect.top}px`);
            });
        }
    }
    
    // Show a visual marker on each cell
    if (confirm('Add position markers to cells?')) {
        cells.forEach((cell, index) => {
            const rowEl = cell.closest('.tabulator-row');
            const rowPosition = Array.from(rowEl.parentNode.children).indexOf(rowEl);
            const field = cell.getAttribute('tabulator-field');
            
            const marker = document.createElement('div');
            marker.style.position = 'absolute';
            marker.style.top = '2px';
            marker.style.right = '2px';
            marker.style.backgroundColor = 'rgba(255, 0, 0, 0.7)';
            marker.style.color = 'white';
            marker.style.fontSize = '9px';
            marker.style.padding = '1px 3px';
            marker.style.borderRadius = '3px';
            marker.style.zIndex = '1000';
            marker.textContent = `${rowPosition}:${field}`;
            
            cell.style.position = 'relative';
            cell.appendChild(marker);
        });
    }
    
    console.groupEnd();
    
    return "Cell position analysis complete. Check the console for details.";
};

// Add a button to trigger the debug function
if (window.location.search.includes('debug=true')) {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            const debugButton = document.createElement('button');
            debugButton.textContent = 'Debug Cell Positions';
            debugButton.style.position = 'fixed';
            debugButton.style.bottom = '10px';
            debugButton.style.left = '150px';
            debugButton.style.zIndex = '9999';
            debugButton.style.padding = '5px 10px';
            debugButton.style.backgroundColor = '#ef4444';
            debugButton.style.color = 'white';
            debugButton.style.border = 'none';
            debugButton.style.borderRadius = '4px';
            debugButton.style.cursor = 'pointer';
            
            debugButton.addEventListener('click', () => {
                window.debugCellPositions();
            });
            
            document.body.appendChild(debugButton);
        }, 2000);
    });
}

/**
 * Helper utilities for debugging cell position issues in collaborative DataFrame editing
 */

// Global state tracking
window.cellPositionHelper = {
    enabled: false,
    indicators: {},
    lastUpdate: 0
};

/**
 * Enable cell position tracking
 */
function enableCellPositionTracking() {
    window.cellPositionHelper.enabled = true;
    
    // Add debug UI
    const debugPanel = document.createElement('div');
    debugPanel.id = 'cell-position-helper-panel';
    debugPanel.style.position = 'fixed';
    debugPanel.style.top = '10px';
    debugPanel.style.right = '10px';
    debugPanel.style.backgroundColor = 'rgba(0,0,0,0.8)';
    debugPanel.style.color = 'white';
    debugPanel.style.padding = '10px';
    debugPanel.style.borderRadius = '5px';
    debugPanel.style.zIndex = '10000';
    debugPanel.style.fontSize = '12px';
    debugPanel.style.maxWidth = '300px';
    
    debugPanel.innerHTML = `
        <div style="margin-bottom:8px;display:flex;justify-content:space-between;">
            <strong>Cell Position Debugger</strong>
            <span id="close-cell-debug" style="cursor:pointer;">&times;</span>
        </div>
        <div id="cell-position-info">Hover over cells to see position</div>
        <div style="margin-top:8px;">
            <button id="show-all-positions">Show All Positions</button>
            <button id="clear-positions">Clear</button>
        </div>
    `;
    
    document.body.appendChild(debugPanel);
    
    // Add event handlers
    document.getElementById('close-cell-debug').addEventListener('click', () => {
        disableCellPositionTracking();
    });
    
    document.getElementById('show-all-positions').addEventListener('click', () => {
        showAllCellPositions();
    });
    
    document.getElementById('clear-positions').addEventListener('click', () => {
        clearCellPositions();
    });
    
    // Add mouse tracking
    document.addEventListener('mousemove', trackMousePosition);
    
    console.log('Cell position debugging enabled!');
    return true;
}

/**
 * Disable cell position tracking
 */
function disableCellPositionTracking() {
    window.cellPositionHelper.enabled = false;
    
    // Remove debug UI
    const panel = document.getElementById('cell-position-helper-panel');
    if (panel) panel.remove();
    
    // Remove indicators
    clearCellPositions();
    
    // Remove mouse tracking
    document.removeEventListener('mousemove', trackMousePosition);
    
    console.log('Cell position debugging disabled!');
    return true;
}

/**
 * Track mouse position over cells
 */
function trackMousePosition(e) {
    if (!window.cellPositionHelper.enabled) return;
    
    const now = Date.now();
    if (now - window.cellPositionHelper.lastUpdate < 100) return; // Throttle updates
    window.cellPositionHelper.lastUpdate = now;
    
    // Find element under cursor
    const element = document.elementFromPoint(e.clientX, e.clientY);
    if (!element) return;
    
    // Check if it's a table cell
    const cell = element.closest('.tabulator-cell');
    if (!cell) {
        document.getElementById('cell-position-info').textContent = 'Not over a cell';
        return;
    }
    
    // Get cell info
    const field = cell.getAttribute('tabulator-field');
    const row = cell.closest('.tabulator-row');
    
    if (!field || !row) {
        document.getElementById('cell-position-info').textContent = 'Invalid cell data';
        return;
    }
    
    // Calculate row position by counting previous siblings
    let rowPosition = 0;
    let current = row;
    while (current.previousElementSibling) {
        current = current.previousElementSibling;
        if (current.classList.contains('tabulator-row')) {
            rowPosition++;
        }
    }
    
    // Try to get cell value 
    const cellValue = cell.textContent || 'empty';
    
    // Update info panel
    document.getElementById('cell-position-info').innerHTML = `
        <div><strong>Position:</strong> ${rowPosition}</div>
        <div><strong>Field:</strong> ${field}</div>
        <div><strong>Value:</strong> ${cellValue}</div>
    `;
    
    // Add indicator if not already there
    const cellId = `${rowPosition}-${field}`;
    if (!window.cellPositionHelper.indicators[cellId]) {
        addPositionIndicator(cell, rowPosition, field);
    }
}

/**
 * Add a position indicator to a cell
 */
function addPositionIndicator(cell, rowPosition, field) {
    const cellId = `${rowPosition}-${field}`;
    
    // Create indicator
    const indicator = document.createElement('div');
    indicator.className = 'cell-position-indicator';
    indicator.textContent = `${rowPosition}:${field}`;
    indicator.style.position = 'absolute';
    indicator.style.top = '0';
    indicator.style.right = '0';
    indicator.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
    indicator.style.color = 'white';
    indicator.style.fontSize = '9px';
    indicator.style.padding = '1px 3px';
    indicator.style.borderRadius = '2px';
    indicator.style.pointerEvents = 'none';
    indicator.style.zIndex = '1000';
    
    // Make sure the cell has position relative
    if (window.getComputedStyle(cell).position === 'static') {
        cell.style.position = 'relative';
    }
    
    cell.appendChild(indicator);
    
    // Store reference
    window.cellPositionHelper.indicators[cellId] = indicator;
    
    return indicator;
}

/**
 * Show position indicators for all cells
 */
function showAllCellPositions() {
    if (!window.cellPositionHelper.enabled) return false;
    
    // Clear existing indicators
    clearCellPositions();
    
    // Get all cells
    const cells = document.querySelectorAll('.tabulator-cell');
    
    cells.forEach(cell => {
        const field = cell.getAttribute('tabulator-field');
        if (!field) return;
        
        const row = cell.closest('.tabulator-row');
        if (!row) return;
        
        // Calculate row position
        let rowPosition = 0;
        let current = row;
        while (current.previousElementSibling) {
            current = current.previousElementSibling;
            if (current.classList.contains('tabulator-row')) {
                rowPosition++;
            }
        }
        
        // Add indicator
        addPositionIndicator(cell, rowPosition, field);
    });
    
    console.log(`Added position indicators to ${Object.keys(window.cellPositionHelper.indicators).length} cells`);
    return true;
}

/**
 * Clear all position indicators
 */
function clearCellPositions() {
    Object.values(window.cellPositionHelper.indicators).forEach(indicator => {
        if (indicator && indicator.parentNode) {
            indicator.parentNode.removeChild(indicator);
        }
    });
    
    window.cellPositionHelper.indicators = {};
    return true;
}

// Initialize when the document is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Check if debug is enabled via URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('debug') === 'positions' || urlParams.get('debug') === 'all') {
        setTimeout(enableCellPositionTracking, 1000);
    }
    
    // Add keyboard shortcut - Ctrl+Alt+P
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.altKey && e.key === 'p') {
            if (window.cellPositionHelper.enabled) {
                disableCellPositionTracking();
            } else {
                enableCellPositionTracking();
            }
        }
    });
});

// Export to global scope
window.cellPositionHelper = {
    ...window.cellPositionHelper,
    enable: enableCellPositionTracking,
    disable: disableCellPositionTracking,
    showAll: showAllCellPositions,
    clear: clearCellPositions
};
