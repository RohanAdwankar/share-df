/**
 * Debugging tool to help with cell positioning issues
 */

function enableTableDebugMode() {
    document.body.classList.add('debug-mode');
    
    // Add row and column positions to cells
    function addPositionIndicators() {
        // Get all cells
        const cells = document.querySelectorAll('.tabulator-cell');
        
        cells.forEach((cell, index) => {
            // Get row and column information
            const row = cell.closest('.tabulator-row');
            const rowPosition = Array.from(row.parentNode.children).indexOf(row);
            
            // Add row position as data attribute
            cell.setAttribute('data-row', rowPosition);
            
            // Add click handler for debugging
            cell.addEventListener('click', function(e) {
                if (e.shiftKey && e.ctrlKey) {
                    e.stopPropagation();
                    console.log(`Cell info: field=${cell.getAttribute('tabulator-field')}, rowPos=${rowPosition}`);
                    
                    // Highlight this cell for debugging
                    highlightCellForDebugging(cell);
                }
            });
        });
    }
    
    // Highlight a specific cell for debugging
    function highlightCellForDebugging(cellElement) {
        // Remove any existing highlight
        const existingHighlight = document.querySelector('.debug-cell-highlight');
        if (existingHighlight) existingHighlight.remove();
        
        // Get cell position and dimensions
        const rect = cellElement.getBoundingClientRect();
        
        // Create highlight element
        const highlight = document.createElement('div');
        highlight.className = 'debug-cell-highlight';
        highlight.style.left = `${rect.left}px`;
        highlight.style.top = `${rect.top}px`;
        highlight.style.width = `${rect.width}px`;
        highlight.style.height = `${rect.height}px`;
        
        // Add cell info
        highlight.innerHTML = `
            <div style="background: black; color: white; font-size: 10px; padding: 2px;">
                Row: ${cellElement.getAttribute('data-row')}<br>
                Field: ${cellElement.getAttribute('tabulator-field')}
            </div>
        `;
        
        // Add to DOM
        document.body.appendChild(highlight);
        
        // Auto-remove after 5 seconds
        setTimeout(() => highlight.remove(), 5000);
    }
    
    // Watch for table changes and update position indicators
    const observer = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            if (mutation.type === 'childList' || mutation.type === 'subtree') {
                setTimeout(addPositionIndicators, 100);
            }
        });
    });
    
    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: false
    });
    
    // Initial setup
    setTimeout(addPositionIndicators, 500);
    
    // Add key command to toggle boundaries
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.shiftKey && e.key === 'B') {
            document.body.classList.toggle('debug-show-boundaries');
        }
    });
    
    console.log('✅ Table Debug Mode Enabled! Use Ctrl+Shift+Click on cells to debug positions');
}

// Check for debug mode in URL
if (window.location.search.includes('debug=cells')) {
    document.addEventListener('DOMContentLoaded', function() {
        // Load debug CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/css/debug.css';
        document.head.appendChild(link);
        
        // Start debugging when table loads
        setTimeout(enableTableDebugMode, 1000);
    });
}
