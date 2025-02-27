/**
 * Connection debugging utilities for the DataFrame Editor
 * 
 * This script helps diagnose WebSocket connection issues and sync problems
 * between collaborators.
 */

class ConnectionDebugger {
    constructor() {
        this.messageLog = [];
        this.maxLogSize = 200;
        this.initialized = false;
        this.panel = null;
        this.syncStatus = {
            lastSent: null,
            lastReceived: null,
            messageCount: 0,
            errorCount: 0,
            reconnectAttempts: 0
        };
    }
    
    init() {
        if (this.initialized) return;
        
        // Create debug UI
        this.createDebugUI();
        
        // Start monitoring connection
        this.monitorConnection();
        
        this.initialized = true;
        
        console.log('[ConnectionDebugger] Initialized');
    }
    
    createDebugUI() {
        // Create main container
        const container = document.createElement('div');
        container.id = 'connection-debug-panel';
        container.style.cssText = `
            position: fixed;
            bottom: 10px;
            left: 10px;
            background-color: rgba(0, 0, 0, 0.85);
            color: #eee;
            font-family: monospace;
            font-size: 12px;
            padding: 10px;
            border-radius: 5px;
            z-index: 10001;
            width: 360px;
            max-height: 200px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
            transition: opacity 0.3s;
            opacity: 0.85;
        `;
        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                <h3 style="margin: 0; font-size: 14px;">Connection Status</h3>
                <div>
                    <button id="conn-debug-test-btn" style="background: #3b82f6; border: none; color: white; border-radius: 3px; padding: 2px 6px; cursor: pointer; font-size: 10px; margin-right: 5px;">Test</button>
                    <button id="conn-debug-close-btn" style="background: #555; border: none; color: white; border-radius: 3px; padding: 2px 6px; cursor: pointer; font-size: 10px;">×</button>
                </div>
            </div>
            <div style="display: flex; margin-bottom: 5px;">
                <div id="conn-status-indicator" style="width: 12px; height: 12px; border-radius: 50%; background-color: gray; margin-right: 8px; margin-top: 2px;"></div>
                <div id="conn-status-text">Checking connection...</div>
            </div>
            <div id="conn-debug-stats" style="font-size: 11px; margin: 5px 0; color: #aaa;">
                Messages: 0 | Errors: 0 | Reconnects: 0
            </div>
            <div id="conn-debug-details" style="font-size: 11px; overflow-y: auto; flex-grow: 1;">
                <div>Initializing connection monitoring...</div>
            </div>
        `;
        
        document.body.appendChild(container);
        this.panel = container;
        
        // Add event listeners
        document.getElementById('conn-debug-close-btn').addEventListener('click', () => {
            container.style.display = 'none';
        });
        
        document.getElementById('conn-debug-test-btn').addEventListener('click', () => {
            this.testConnection();
        });
        
        // Add hover effects for better UX
        container.addEventListener('mouseenter', () => {
            container.style.opacity = '1';
        });
        
        container.addEventListener('mouseleave', () => {
            container.style.opacity = '0.85';
        });
    }
    
    monitorConnection() {
        // Check if we have a WebSocket already
        const checkWebSocket = () => {
            const ws = this.findWebSocket();
            if (ws) {
                this.attachWebSocketMonitors(ws);
                this.updateStatus('connected', 'Connected to server');
            } else {
                this.updateStatus('disconnected', 'No WebSocket connection found');
                
                // Try again in 2 seconds
                setTimeout(checkWebSocket, 2000);
            }
        };
        
        // Start checking
        checkWebSocket();
        
        // Also look for Alpine.js instance
        this.monitorAlpineApp();
    }
    
    findWebSocket() {
        // Try to find the WebSocket from our Alpine app
        if (window.editorApp && window.editorApp.socket && 
            window.editorApp.socket instanceof WebSocket) {
            return window.editorApp.socket;
        }
        
        // Try to find it in common variables
        if (window.socket && window.socket instanceof WebSocket) {
            return window.socket;
        }
        
        return null;
    }
    
    attachWebSocketMonitors(ws) {
        // Save original methods
        const originalSend = ws.send;
        const originalClose = ws.close;
        
        // Override send
        ws.send = (data) => {
            this.logMessage('outgoing', data);
            this.syncStatus.lastSent = new Date();
            this.syncStatus.messageCount++;
            this.updateStats();
            return originalSend.apply(ws, arguments);
        };
        
        // Add event listeners
        ws.addEventListener('message', (event) => {
            this.logMessage('incoming', event.data);
            this.syncStatus.lastReceived = new Date();
            this.syncStatus.messageCount++;
            this.updateStats();
        });
        
        ws.addEventListener('close', () => {
            this.updateStatus('disconnected', 'Connection closed');
        });
        
        ws.addEventListener('error', (error) => {
            this.syncStatus.errorCount++;
            this.updateStats();
            this.addDetail(`Error: ${error}`, 'error');
            this.updateStatus('error', 'Connection error');
        });
    }
    
    monitorAlpineApp() {
        // Use MutationObserver to watch for Alpine components
        const observer = new MutationObserver((mutations) => {
            if (window.editorApp && !this._alpineMonitored) {
                this._alpineMonitored = true;
                this.addDetail('Alpine.js editorApp detected', 'info');
                
                // Watch for collaborators changes
                if (window.editorApp.collaborators) {
                    this.addDetail(`Found ${Object.keys(window.editorApp.collaborators).length} collaborators`, 'info');
                    
                    // Set up a watcher for changes
                    setInterval(() => {
                        const count = Object.keys(window.editorApp.collaborators || {}).length;
                        document.getElementById('conn-debug-stats').innerHTML = 
                            `Messages: ${this.syncStatus.messageCount} | Errors: ${this.syncStatus.errorCount} | ` + 
                            `Reconnects: ${this.syncStatus.reconnectAttempts} | Collaborators: ${count}`;
                    }, 2000);
                }
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['x-data']
        });
    }
    
    logMessage(direction, data) {
        try {
            let parsedData;
            if (typeof data === 'string') {
                parsedData = JSON.parse(data);
            } else {
                parsedData = data;
            }
            
            // Add to log with timestamp
            this.messageLog.push({
                timestamp: new Date(),
                direction,
                data: parsedData
            });
            
            // Trim log if needed
            if (this.messageLog.length > this.maxLogSize) {
                this.messageLog.shift();
            }
            
            // Add to UI if it's interesting
            if (parsedData.type && 
                ['cell_edit', 'add_column', 'add_row', 'error'].includes(parsedData.type)) {
                this.addDetail(
                    `${direction === 'incoming' ? '←' : '→'} ${parsedData.type}: ${JSON.stringify(parsedData).slice(0, 40)}...`,
                    direction === 'incoming' ? 'received' : 'sent'
                );
            }
        } catch (e) {
            console.log('Could not parse message data', e);
        }
    }
    
    updateStatus(status, message) {
        const indicator = document.getElementById('conn-status-indicator');
        const statusText = document.getElementById('conn-status-text');
        
        if (!indicator || !statusText) return;
        
        // Update indicator color
        switch (status) {
            case 'connected':
                indicator.style.backgroundColor = '#10b981'; // green
                break;
            case 'disconnected':
                indicator.style.backgroundColor = '#ef4444'; // red
                break;
            case 'error':
                indicator.style.backgroundColor = '#f59e0b'; // orange/amber
                break;
            default:
                indicator.style.backgroundColor = '#6b7280'; // gray
        }
        
        // Update status text
        statusText.textContent = message;
    }
    
    updateStats() {
        const statsElement = document.getElementById('conn-debug-stats');
        if (statsElement) {
            statsElement.innerHTML = 
                `Messages: ${this.syncStatus.messageCount} | Errors: ${this.syncStatus.errorCount} | ` + 
                `Reconnects: ${this.syncStatus.reconnectAttempts}`;
        }
    }
    
    addDetail(message, type = 'info') {
        const detailsElement = document.getElementById('conn-debug-details');
        if (!detailsElement) return;
        
        // Create timestamp
        const timestamp = new Date().toTimeString().split(' ')[0];
        
        // Create new detail element with appropriate color
        const detail = document.createElement('div');
        detail.style.marginBottom = '2px';
        detail.style.fontSize = '10px';
        detail.style.borderLeft = '2px solid';
        detail.style.paddingLeft = '5px';
        
        // Set color based on type
        switch (type) {
            case 'error':
                detail.style.borderColor = '#ef4444';
                detail.style.color = '#fca5a5';
                break;
            case 'received':
                detail.style.borderColor = '#10b981';
                detail.style.color = '#d1fae5';
                break;
            case 'sent':
                detail.style.borderColor = '#3b82f6';
                detail.style.color = '#bfdbfe';
                break;
            case 'info':
            default:
                detail.style.borderColor = '#6b7280';
                detail.style.color = '#d1d5db';
        }
        
        detail.textContent = `[${timestamp}] ${message}`;
        
        // Add to details panel
        detailsElement.appendChild(detail);
        
        // Scroll to bottom
        detailsElement.scrollTop = detailsElement.scrollHeight;
        
        // Limit number of details
        if (detailsElement.children.length > 50) {
            detailsElement.removeChild(detailsElement.children[0]);
        }
    }
    
    testConnection() {
        const ws = this.findWebSocket();
        if (!ws) {
            this.addDetail('No WebSocket connection found', 'error');
            return;
        }
        
        try {
            // Send a ping message
            ws.send(JSON.stringify({
                type: "debug_ping",
                timestamp: Date.now()
            }));
            
            this.addDetail('Sent ping message', 'info');
        } catch (e) {
            this.addDetail(`Failed to send test message: ${e.message}`, 'error');
        }
    }
}

// Initialize only if in debug mode
if (window.location.search.includes('debug=conn') || 
    window.location.search.includes('debug=true') || 
    window.location.search.includes('debug=all')) {
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.connectionDebugger = new ConnectionDebugger();
            window.connectionDebugger.init();
        });
    } else {
        window.connectionDebugger = new ConnectionDebugger();
        window.connectionDebugger.init();
    }
}

// Export for manual use
window.ConnectionDebugger = ConnectionDebugger;
