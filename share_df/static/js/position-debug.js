
/**
 * Debug utility for cell position troubleshooting in collaborative editing
 */

// Global debug flag
window.debugPositions = false;

// Enable position debug mode
function enablePositionDebug() {
    window.debugPositions = true;
    console.log('Cell position debug mode enabled');
    
    // Add visual indicators to all cells
    setTimeout(addCellPositionIndicators, 500);
    
    // Watch for table changes and update indicators
    const observer = new MutationObserver((mutations) => {
        if (mutations.some(m => m.type === 'childList' || m.type === 'subtree')) {
            setTimeout(addCellPositionIndicators, 100);
        }
    });
    
    observer.observe(document.getElementById('data-table'), {
        childList: true,
        subtree: true
    });
    
    // Add debug toggle button
    addDebugButton();
}

// Add position indicators to all cells
function addCellPositionIndicators() {
    if (!window.debugPositions) return;
    
    // Remove existing indicators
    document.querySelectorAll('.position-indicator').forEach(el => el.remove());
    
    // Get all cells
    const cellElements = document.querySelectorAll('.tabulator-cell');
    const cellsByField = {};
    
    // Group cells by field
    cellElements.forEach(cell => {
        const field = cell.getAttribute('tabulator-field');
        if (!field) return;
        
        if (!cellsByField[field]) {
            cellsByField[field] = [];
        }
        
        cellsByField[field].push(cell);
    });
    
    // Add position indicators
    for (const [field, cells] of Object.entries(cellsByField)) {
        cells.forEach((cell, index) => {
            // Create indicator
            const indicator = document.createElement('div');
            indicator.classList.add('position-indicator');
            indicator.textContent = `${index}:${field}`;
            indicator.style.position = 'absolute';
            indicator.style.top = '0';
            indicator.style.right = '0';
            indicator.style.fontSize = '8px';
            indicator.style.padding = '1px 3px';
            indicator.style.backgroundColor = 'rgba(255, 0, 0, 0.7)';
            indicator.style.color = 'white';
            indicator.style.zIndex = '1000';
            indicator.style.pointerEvents = 'none';
            indicator.style.borderRadius = '2px';
            
            // Make sure cell position is relative
            if (window.getComputedStyle(cell).position === 'static') {
                cell.style.position = 'relative';
            }
            
            cell.appendChild(indicator);
            
            // Add click handler for debug info
            cell.addEventListener('click', (e) => {
                if (e.shiftKey && e.altKey) {
                    console.log(`Cell: field=${field}, index=${index}, content=${cell.innerText}`);
                    e.stopPropagation();
                }
            });
        });
    }
    
    console.log('Added position indicators to cells');
}

// Add debug button
function addDebugButton() {
    const btnExists = document.getElementById('position-debug-btn');
    if (btnExists) return;
    
    const btn = document.createElement('button');
    btn.id = 'position-debug-btn';
    btn.textContent = window.debugPositions ? 'Disable Position Debug' : 'Enable Position Debug';
    btn.style.position = 'fixed';
    btn.style.bottom = '10px';
    btn.style.left = '10px';
    btn.style.zIndex = '9999';
    btn.style.padding = '5px 10px';
    btn.style.backgroundColor = window.debugPositions ? '#ef4444' : '#3b82f6';
    btn.style.color = 'white';
    btn.style.border = 'none';
    btn.style.borderRadius = '4px';
    
    btn.addEventListener('click', () => {
        window.debugPositions = !window.debugPositions;
        btn.textContent = window.debugPositions ? 'Disable Position Debug' : 'Enable Position Debug';
        btn.style.backgroundColor = window.debugPositions ? '#ef4444' : '#3b82f6';
        
        if (window.debugPositions) {
            addCellPositionIndicators();
        } else {
            document.querySelectorAll('.position-indicator').forEach(el => el.remove());
        }
    });
    
    document.body.appendChild(btn);
}

// Check URL for debug flag
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (window.location.search.includes('debug=positions') || 
            window.location.search.includes('debug=all')) {
            setTimeout(enablePositionDebug, 1000);
        } else {
            // Add a hidden shortcut (Ctrl+Shift+P)
            document.addEventListener('keydown', (e) => {
                if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'p') {
                    enablePositionDebug();
                    e.preventDefault();
                }
            });
        }
    });
} else if (window.location.search.includes('debug=positions') || 
           window.location.search.includes('debug=all')) {
    setTimeout(enablePositionDebug, 1000);
}

// Export globally
window.enablePositionDebug = enablePositionDebug;
