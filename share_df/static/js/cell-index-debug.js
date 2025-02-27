/**
 * Debug utility to visualize table cell indices
 * This helps diagnose row/column index mismatch issues
 */

function enableCellIndexVisualization() {
    // Get all cells
    const cells = document.querySelectorAll('.tabulator-cell');
    console.log(`Found ${cells.length} cells to index`);
    
    // Get header cells too
    const headerCells = document.querySelectorAll('.tabulator-col');
    console.log(`Found ${headerCells.length} header cells`);
    
    // Map all cell positions
    const cellMap = {};
    
    cells.forEach((cell) => {
        const field = cell.getAttribute('tabulator-field');
        if (!field) return; // Skip cells without field attribute
        
        // Find the row element
        const row = cell.closest('.tabulator-row');
        if (!row) return;
        
        // Get row position by counting previous siblings
        let rowPosition = 0;
        let prevRow = row.previousElementSibling;
        while (prevRow) {
            if (prevRow.classList.contains('tabulator-row')) {
                rowPosition++;
            }
            prevRow = prevRow.previousElementSibling;
        }
        
        // Store cell position
        if (!cellMap[field]) {
            cellMap[field] = [];
        }
        
        cellMap[field].push({
            element: cell,
            row: rowPosition,
            content: cell.textContent
        });
        
        // Add a label to the cell showing its position
        const label = document.createElement('div');
        label.style.position = 'absolute';
        label.style.top = '1px';
        label.style.left = '1px';
        label.style.fontSize = '8px';
        label.style.padding = '1px';
        label.style.background = 'rgba(0,0,0,0.5)';
        label.style.color = 'white';
        label.style.borderRadius = '2px';
        label.style.zIndex = '999';
        label.style.pointerEvents = 'none';
        label.textContent = `R${rowPosition}:${field}`;
        
        // Make sure the cell has relative positioning
        if (window.getComputedStyle(cell).position === 'static') {
            cell.style.position = 'relative';
        }
        
        cell.appendChild(label);
    });
    
    // Log the cell map
    console.table(Object.entries(cellMap).map(([field, cells]) => ({
        field,
        count: cells.length,
        rows: cells.map(c => c.row).join(', '),
    })));
    
    return "Cell indices visualization enabled";
}

// Add a button to toggle the visualization
function addCellIndexVisButton() {
    const button = document.createElement('button');
    button.innerText = 'Show Cell Indices';
    button.style.position = 'fixed';
    button.style.bottom = '10px';
    button.style.right = '10px';
    button.style.padding = '5px 10px';
    button.style.zIndex = '9999';
    button.style.backgroundColor = '#3b82f6';
    button.style.color = 'white';
    button.style.border = 'none';
    button.style.borderRadius = '4px';
    
    button.addEventListener('click', () => {
        enableCellIndexVisualization();
        button.disabled = true;
        button.innerText = 'Indices Shown';
    });
    
    document.body.appendChild(button);
}

// Auto-initialize when URL has appropriate flag
if (window.location.search.includes('debug=indices') || 
    window.location.search.includes('debug=all')) {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(addCellIndexVisButton, 1000);
    });
}

// Export for manual use
window.showCellIndices = enableCellIndexVisualization;
