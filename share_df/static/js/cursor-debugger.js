/**
 * Simple cursor position debugger for collaborative editing
 * 
 * Usage: Add ?debug=cursor to the URL to enable this debugger
 */

(function() {
    if (!window.location.search.includes('debug=cursor')) {
        console.log("Cursor debugger not enabled. Add ?debug=cursor to URL to enable.");
        return;
    }
    
    console.log("🔍 Cursor position debugger loaded");
    
    // Wait for the table to be initialized
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(initDebugger, 2000);
    });
    
    function initDebugger() {
        // Check if the table exists
        const tableElement = document.getElementById("data-table");
        if (!tableElement) {
            console.error("Table element not found. Cursor debugger cannot initialize.");
            return;
        }
        
        console.log("Table found, initializing cursor debugger...");
        
        // Add debug overlay
        const overlay = document.createElement('div');
        overlay.style.position = 'fixed';
        overlay.style.top = '10px';
        overlay.style.left = '10px';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        overlay.style.color = 'white';
        overlay.style.padding = '10px';
        overlay.style.borderRadius = '5px';
        overlay.style.fontSize = '12px';
        overlay.style.fontFamily = 'monospace';
        overlay.style.zIndex = '10000';
        overlay.style.maxWidth = '300px';
        overlay.style.display = 'none'; // Start hidden
        
        overlay.innerHTML = `
            <div><strong>Cursor Debug</strong> <button id="close-debug">×</button></div>
            <div id="debug-position">No position data</div>
            <div id="debug-cell">No cell data</div>
            <div id="debug-element">No element data</div>
            <button id="test-ping">Test WebSocket</button>
        `;
        
        document.body.appendChild(overlay);
        
        // Add toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.textContent = 'Cursor Debug';
        toggleBtn.style.position = 'fixed';
        toggleBtn.style.bottom = '10px';
        toggleBtn.style.left = '10px';
        toggleBtn.style.padding = '5px 10px';
        toggleBtn.style.backgroundColor = '#3b82f6';
        toggleBtn.style.color = 'white';
        toggleBtn.style.border = 'none';
        toggleBtn.style.borderRadius = '4px';
        toggleBtn.style.zIndex = '9999';
        
        document.body.appendChild(toggleBtn);
        
        // Toggle debug overlay
        toggleBtn.addEventListener('click', function() {
            if (overlay.style.display === 'none') {
                overlay.style.display = 'block';
            } else {
                overlay.style.display = 'none';
            }
        });
        
        // Close debug overlay
        document.getElementById('close-debug').addEventListener('click', function() {
            overlay.style.display = 'none';
        });
        
        // Test WebSocket connection
        document.getElementById('test-ping').addEventListener('click', function() {
            if (window.editorApp) {
                window.editorApp.sendDebugPing();
                overlay.querySelector('#debug-position').textContent = 'Sent ping, check console...';
            } else {
                overlay.querySelector('#debug-position').textContent = 'editorApp not found!';
            }
        });
        
        // Track mouse movement
        document.addEventListener('mousemove', function(e) {
            if (overlay.style.display === 'none') return;
            
            // Update position data
            overlay.querySelector('#debug-position').textContent = `Mouse: x=${e.clientX}, y=${e.clientY}`;
            
            // Find element under cursor
            const element = document.elementFromPoint(e.clientX, e.clientY);
            if (element) {
                overlay.querySelector('#debug-element').textContent = `Element: ${element.tagName} [${Array.from(element.classList).join(', ')}]`;
                
                // Find table cell
                const cell = element.closest('.tabulator-cell');
                if (cell) {
                    const field = cell.getAttribute('tabulator-field');
                    const row = cell.closest('.tabulator-row');
                    let rowIndex = 0;
                    let current = row;
                    
                    while (current.previousElementSibling) {
                        current = current.previousElementSibling;
                        if (current.classList.contains('tabulator-row')) {
                            rowIndex++;
                        }
                    }
                    
                    overlay.querySelector('#debug-cell').innerHTML = `
                        <strong>Cell:</strong> row=${rowIndex}, field=${field}<br>
                        <strong>Tabulator API:</strong> ${cell.getAttribute('tabulator-row') || 'N/A'}, ${field || 'N/A'}<br>
                        <strong>Content:</strong> ${cell.textContent}
                    `;
                } else {
                    overlay.querySelector('#debug-cell').textContent = 'Not over a table cell';
                }
            } else {
                overlay.querySelector('#debug-element').textContent = 'No element found';
                overlay.querySelector('#debug-cell').textContent = 'No cell data';
            }
        });
        
        console.log("Cursor debugger initialized. Click the 'Cursor Debug' button to toggle debugging.");
    }
})();
