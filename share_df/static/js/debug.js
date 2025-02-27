/**
 * Debugging utilities for share-df
 */

// Create a debug panel that shows recent WebSocket messages
function createDebugPanel() {
    const debugPanel = document.createElement('div');
    debugPanel.id = 'debug-panel';
    debugPanel.style.position = 'fixed';
    debugPanel.style.bottom = '10px';
    debugPanel.style.right = '10px';
    debugPanel.style.width = '300px';
    debugPanel.style.maxHeight = '200px';
    debugPanel.style.overflowY = 'auto';
    debugPanel.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
    debugPanel.style.color = '#eee';
    debugPanel.style.padding = '10px';
    debugPanel.style.borderRadius = '5px';
    debugPanel.style.fontFamily = 'monospace';
    debugPanel.style.fontSize = '10px';
    debugPanel.style.zIndex = 10000;
    
    // Add header with controls
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.marginBottom = '5px';
    
    const title = document.createElement('div');
    title.textContent = 'WebSocket Debug';
    title.style.fontWeight = 'bold';
    
    const clearBtn = document.createElement('button');
    clearBtn.textContent = 'Clear';
    clearBtn.style.padding = '2px 5px';
    clearBtn.style.fontSize = '10px';
    clearBtn.style.backgroundColor = '#444';
    clearBtn.style.color = '#fff';
    clearBtn.style.border = 'none';
    clearBtn.style.borderRadius = '3px';
    clearBtn.style.cursor = 'pointer';
    clearBtn.onclick = () => {
        const log = document.getElementById('debug-log');
        if (log) log.innerHTML = '';
    };
    
    header.appendChild(title);
    header.appendChild(clearBtn);
    debugPanel.appendChild(header);
    
    // Add log container
    const log = document.createElement('div');
    log.id = 'debug-log';
    log.style.height = '160px';
    log.style.overflowY = 'auto';
    debugPanel.appendChild(log);
    
    document.body.appendChild(debugPanel);
    
    // Add drag functionality
    let isDragging = false;
    let offsetX, offsetY;
    
    header.style.cursor = 'move';
    header.addEventListener('mousedown', (e) => {
        isDragging = true;
        offsetX = e.clientX - debugPanel.getBoundingClientRect().left;
        offsetY = e.clientY - debugPanel.getBoundingClientRect().top;
    });
    
    document.addEventListener('mousemove', (e) => {
        if (isDragging) {
            debugPanel.style.left = (e.clientX - offsetX) + 'px';
            debugPanel.style.top = (e.clientY - offsetY) + 'px';
            debugPanel.style.right = 'auto';
            debugPanel.style.bottom = 'auto';
        }
    });
    
    document.addEventListener('mouseup', () => {
        isDragging = false;
    });
    
    return debugPanel;
}

// Log a message to the debug panel
function logMessage(direction, type, data) {
    const log = document.getElementById('debug-log');
    if (!log) return;
    
    const entry = document.createElement('div');
    entry.style.margin = '2px 0';
    entry.style.padding = '3px';
    entry.style.borderLeft = `3px solid ${direction === 'in' ? '#4CAF50' : '#2196F3'}`;
    entry.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
    
    const timestamp = new Date().toISOString().split('T')[1].substring(0, 8);
    const directionSymbol = direction === 'in' ? '← ' : '→ ';
    
    entry.innerHTML = `<span style="color: #888">${timestamp}</span> <strong style="color: ${direction === 'in' ? '#4CAF50' : '#2196F3'}">${directionSymbol}${type}</strong>`;
    
    if (data && typeof data === 'object') {
        const details = document.createElement('pre');
        details.style.margin = '2px 0';
        details.style.padding = '2px 5px';
        details.style.backgroundColor = 'rgba(0, 0, 0, 0.2)';
        details.style.maxHeight = '60px';
        details.style.overflow = 'auto';
        details.style.fontSize = '9px';
        details.textContent = JSON.stringify(data, null, 2);
        entry.appendChild(details);
    }
    
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
    
    // Keep only most recent 50 entries
    while (log.children.length > 50) {
        log.removeChild(log.firstChild);
    }
}

// Override WebSocket methods to log messages
function patchWebSocket() {
    const originalSend = WebSocket.prototype.send;
    WebSocket.prototype.send = function(data) {
        try {
            const parsedData = JSON.parse(data);
            logMessage('out', parsedData.type, parsedData);
        } catch (e) {
            logMessage('out', 'binary/text', { length: data.length });
        }
        return originalSend.apply(this, arguments);
    };
    
    // Store references to the original methods
    const originalAddEventListener = WebSocket.prototype.addEventListener;
    
    // Override addEventListener to capture message events
    WebSocket.prototype.addEventListener = function(type, listener, options) {
        if (type === 'message') {
            const wrappedListener = function(event) {
                try {
                    const parsedData = JSON.parse(event.data);
                    logMessage('in', parsedData.type, parsedData);
                } catch (e) {
                    logMessage('in', 'binary/text', { length: event.data.length });
                }
                return listener.apply(this, arguments);
            };
            return originalAddEventListener.call(this, type, wrappedListener, options);
        }
        return originalAddEventListener.apply(this, arguments);
    };
}

// Initialize debug tools when in development mode
function initDebugTools() {
    // Check if we're in a development context
    const isDebug = 
        window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1' ||
        window.location.search.includes('debug=true');
    
    if (isDebug) {
        console.log('Initializing debug tools for share-df');
        createDebugPanel();
        patchWebSocket();
        
        // Add keyboard shortcut to toggle panel visibility
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.code === 'KeyD') {
                const panel = document.getElementById('debug-panel');
                if (panel) {
                    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
                }
            }
        });
    }
}

// Auto-initialize when the page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDebugTools);
} else {
    initDebugTools();
}
