
/**
 * Debug initialization script
 * Add this to your editor template to enable all debugging tools
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if debug mode is requested via URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const debugMode = urlParams.get('debug');
    
    if (debugMode) {
        console.log('Debug mode enabled:', debugMode);
        
        // Add debug CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/css/debug.css';
        document.head.appendChild(link);
        
        // Add debug class to body
        document.body.classList.add('debug-mode');
        
        // Load appropriate debug tools based on mode
        if (debugMode === 'all' || debugMode === 'true') {
            // Load all debug tools
            loadScript('/static/js/cell-position-helper.js');
            loadScript('/static/js/cell-position-debug.js');
            loadScript('/static/js/cell-index-debug.js');
            loadScript('/static/js/cell-debug.js');
            loadScript('/static/js/table-monitor.js', initTableMonitor);
        } else if (debugMode === 'cells') {
            loadScript('/static/js/cell-position-debug.js');
        } else if (debugMode === 'indices') {
            loadScript('/static/js/cell-index-debug.js');
        } else if (debugMode === 'table') {
            loadScript('/static/js/table-monitor.js', initTableMonitor);
        }
        
        // Add debug button
        const debugBtn = document.createElement('button');
        debugBtn.textContent = 'Debug Panel';
        debugBtn.style.position = 'fixed';
        debugBtn.style.bottom = '10px';
        debugBtn.style.right = '10px';
        debugBtn.style.padding = '8px 12px';
        debugBtn.style.backgroundColor = '#ef4444';
        debugBtn.style.color = 'white';
        debugBtn.style.border = 'none';
        debugBtn.style.borderRadius = '4px';
        debugBtn.style.zIndex = '9999';
        debugBtn.style.fontWeight = 'bold';
        debugBtn.style.cursor = 'pointer';
        
        debugBtn.addEventListener('click', showDebugPanel);
        document.body.appendChild(debugBtn);
    }
});

// Helper to load a script
function loadScript(url, callback) {
    const script = document.createElement('script');
    script.src = url;
    script.onload = callback;
    document.head.appendChild(script);
}

// Initialize table monitor
function initTableMonitor() {
    setTimeout(() => {
        if (window.editorApp && window.editorApp.table) {
            window.tableMonitor = new TableMonitor(window.editorApp.table);
            window.tableMonitor.start();
            console.log('Table monitor initialized');
        } else {
            console.warn('Could not initialize table monitor - table not found');
        }
    }, 2000); // Wait for table to initialize
}

// Show debug panel
function showDebugPanel() {
    // Remove existing panel if any
    const existingPanel = document.getElementById('main-debug-panel');
    if (existingPanel) {
        existingPanel.remove();
        return;
    }
    
    const panel = document.createElement('div');
    panel.id = 'main-debug-panel';
    panel.className = 'debug-panel';
    panel.innerHTML = `
        <h3>Debug Tools</h3>
        <section>
            <button id="debug-table-check">Check Table</button>
            <button id="debug-show-indices">Show Cell Indices</button>
            <button id="debug-highlight-boundaries">Show Boundaries</button>
            <button id="debug-fix-ids" class="success">Fix Row IDs</button>
        </section>
        <section id="debug-metrics"></section>
        <section>
            <h4>Issues</h4>
            <div id="debug-issues">No issues detected</div>
        </section>
        <section>
            <button id="debug-panel-close" class="danger">Close</button>
        </section>
    `;
    
    document.body.appendChild(panel);
    
    // Add event handlers
    document.getElementById('debug-panel-close').addEventListener('click', () => panel.remove());
    
    document.getElementById('debug-table-check').addEventListener('click', () => {
        if (window.tableMonitor) {
            window.tableMonitor.checkTableHealth(true);
            updateDebugMetrics();
        } else if (window.editorApp && window.editorApp.table) {
            window.tableMonitor = new TableMonitor(window.editorApp.table);
            window.tableMonitor.start();
            updateDebugMetrics();
        } else {
            alert('Table not available');
        }
    });
    
    document.getElementById('debug-show-indices').addEventListener('click', () => {
        if (window.showCellIndices) {
            window.showCellIndices();
        } else if (typeof enableCellIndexVisualization === 'function') {
            enableCellIndexVisualization();
        } else {
            loadScript('/static/js/cell-index-debug.js', () => {
                if (typeof enableCellIndexVisualization === 'function') {
                    enableCellIndexVisualization();
                }
            });
        }
    });
    
    document.getElementById('debug-highlight-boundaries').addEventListener('click', () => {
        document.body.classList.toggle('debug-show-boundaries');
    });
    
    document.getElementById('debug-fix-ids').addEventListener('click', () => {
        if (window.tableMonitor) {
            const fixed = window.tableMonitor.fixDuplicateRowIds();
            alert(`Fixed ${fixed} row ID issues`);
            updateDebugMetrics();
        } else {
            alert('Table monitor not initialized');
        }
    });
    
    updateDebugMetrics();
}

function updateDebugMetrics() {
    if (!window.tableMonitor) return;
    
    const metrics = window.tableMonitor.getHealthMetrics();
    const metricsEl = document.getElementById('debug-metrics');
    
    if (!metricsEl) return;
    
    metricsEl.innerHTML = `
        <h4>Table Metrics</h4>
        <div class="debug-metric">
            <span>Status:</span>
            <span class="debug-metric-value" style="color:${metrics.status === 'healthy' ? '#10b981' : '#ef4444'}">
                ${metrics.status}
            </span>
        </div>
        <div class="debug-metric">
            <span>Row count:</span>
            <span class="debug-metric-value">${metrics.rowCount}</span>
        </div>
        <div class="debug-metric">
            <span>Unique row IDs:</span>
            <span class="debug-metric-value">${metrics.uniqueRowIds} / ${metrics.rowCount}</span>
        </div>
        <div class="debug-metric">
            <span>Issues detected:</span>
            <span class="debug-metric-value">${metrics.issuesFound}</span>
        </div>
        <div class="debug-metric">
            <span>Last checked:</span>
            <span class="debug-metric-value">${metrics.lastCheck ? new Date(metrics.lastCheck).toLocaleTimeString() : 'Never'}</span>
        </div>
    `;
}
