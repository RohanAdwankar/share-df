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
