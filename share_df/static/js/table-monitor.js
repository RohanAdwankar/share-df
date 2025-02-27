/**
 * Table Monitor - A utility to validate table state and detect synchronization issues
 */

class TableMonitor {
    constructor(table, options = {}) {
        this.table = table;
        this.options = {
            checkInterval: 5000,  // Check every 5 seconds
            rowIdKey: "_row_id",  // Key for unique row ID
            debug: true,         // Enable debug output
            ...options
        };
        
        this.metrics = {
            checksRun: 0,
            issuesFound: 0,
            lastCheckTime: null,
            rowCount: 0,
            uniqueRowIds: 0,
        };
        
        this.intervalId = null;
    }
    
    start() {
        this.log("Table monitor starting");
        this.initialCheck();
        
        // Set up regular interval checks
        this.intervalId = setInterval(() => {
            this.checkTableHealth();
        }, this.options.checkInterval);
        
        // Add event listeners to key table events
        if (this.table) {
            this.table.on("rowAdded", (row) => {
                this.log(`Row added at position: ${row.getPosition()}, ID: ${row.getData()[this.options.rowIdKey] || 'unknown'}`);
                this.validateRow(row);
            });
            
            this.table.on("dataChanged", () => {
                this.log("Table data changed, scheduling validation");
                // Defer validation to allow table to stabilize
                setTimeout(() => this.checkTableHealth(), 500);
            });
            
            this.table.on("tableBuilt", () => {
                this.log("Table rebuilt, running validation");
                this.initialCheck();
            });
        }
        
        return this;
    }
    
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
            this.log("Table monitor stopped");
        }
        return this;
    }
    
    initialCheck() {
        this.log("Running initial table check");
        this.checkTableHealth(true);
    }
    
    checkTableHealth(isInitial = false) {
        if (!this.table) return;
        
        this.metrics.checksRun++;
        this.metrics.lastCheckTime = new Date();
        
        try {
            const rows = this.table.getRows();
            this.metrics.rowCount = rows.length;
            
            // Check for duplicate row IDs
            const rowIds = rows.map(row => {
                const data = row.getData();
                return data && data[this.options.rowIdKey];
            }).filter(id => id); // Filter out undefined/null IDs
            
            const uniqueIds = new Set(rowIds);
            this.metrics.uniqueRowIds = uniqueIds.size;
            
            if (uniqueIds.size !== rowIds.length) {
                this.reportIssue("DUPLICATE_ROW_IDS", {
                    message: `Found ${rowIds.length - uniqueIds.size} duplicate row IDs`,
                    rowIds: rowIds,
                    uniqueIds: Array.from(uniqueIds)
                });
            }
            
            // Check DOM vs data model consistency
            const domRows = document.querySelectorAll('.tabulator-row:not(.tabulator-calcs)').length;
            if (domRows !== rows.length) {
                this.reportIssue("DOM_DATA_MISMATCH", {
                    message: `DOM row count (${domRows}) doesn't match data model row count (${rows.length})`,
                    domRows,
                    dataRows: rows.length
                });
            }
            
            // Check the first few rows in detail
            const sampleSize = Math.min(3, rows.length);
            for (let i = 0; i < sampleSize; i++) {
                this.validateRow(rows[i]);
            }
            
            // Log success if no issues were found during this check
            if (isInitial || this.options.debug) {
                this.log(`Table health check completed: ${rows.length} rows, ${uniqueIds.size} unique IDs`);
            }
            
        } catch (error) {
            this.reportIssue("CHECK_ERROR", {
                message: `Error during table health check: ${error.message}`,
                stack: error.stack
            });
        }
    }
    
    validateRow(row) {
        try {
            const position = row.getPosition();
            const data = row.getData();
            
            // Check for missing row ID
            if (!data || !data[this.options.rowIdKey]) {
                this.reportIssue("MISSING_ROW_ID", {
                    message: `Row at position ${position} is missing a row ID`,
                    rowPosition: position,
                    rowData: data
                });
            }
        } catch (error) {
            this.reportIssue("VALIDATION_ERROR", {
                message: `Error validating row at position ${row.getPosition()}: ${error.message}`,
                stack: error.stack
            });
        }
    }
    
    reportIssue(type, details) {
        this.metrics.issuesFound++;
        this.log(`Issue detected: ${type}`, details);
    }
    
    log(message, details) {
        if (this.options.debug) {
            console.log(`[TableMonitor] ${message}`, details || '');
        }
    }

    // Add methods to fix issues
    fixDuplicateRowIds() {
        this.log("Attempting to fix duplicate row IDs");
        
        try {
            const rows = this.table.getRows();
            const usedIds = new Set();
            let fixedCount = 0;
            
            rows.forEach((row, index) => {
                const data = row.getData();
                const currentId = data[this.options.rowIdKey];
                
                // If ID doesn't exist or is duplicate, assign a new one
                if (!currentId || usedIds.has(currentId)) {
                    const newId = `row_${Date.now()}_${index}_${Math.random().toString(36).substr(2, 5)}`;
                    data[this.options.rowIdKey] = newId;
                    row.update(data);
                    usedIds.add(newId);
                    fixedCount++;
                } else {
                    usedIds.add(currentId);
                }
            });
            
            this.log(`Fixed ${fixedCount} duplicate/missing row IDs`);
            return fixedCount;
        } catch (error) {
            this.reportIssue("FIX_ERROR", {
                message: `Error fixing duplicate row IDs: ${error.message}`,
                stack: error.stack
            });
            return 0;
        }
    }

    fixDomDataMismatch() {
        this.log("Attempting to fix DOM/data model mismatch");
        
        try {
            const data = this.table.getData();
            
            // Force a full redraw of the table
            this.table.setData(data);
            
            this.log("Table redrawn to fix DOM/data mismatch");
            return true;
        } catch (error) {
            this.reportIssue("FIX_ERROR", {
                message: `Error fixing DOM/data mismatch: ${error.message}`,
                stack: error.stack
            });
            return false;
        }
    }

    generateRowId() {
        return `row_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // Reporting and visualization
    getHealthMetrics() {
        return {
            ...this.metrics,
            status: this.metrics.issuesFound > 0 ? "unhealthy" : "healthy",
            lastCheck: this.metrics.lastCheckTime ? this.metrics.lastCheckTime.toISOString() : null
        };
    }

    visualizeRowIds(displayMode = "tooltip") {
        this.log("Visualizing row IDs");
        
        try {
            // Remove any existing visualizations
            document.querySelectorAll(".table-monitor-row-id").forEach(el => el.remove());
            
            const rows = this.table.getRows();
            
            rows.forEach((row, index) => {
                const data = row.getData();
                const id = data[this.options.rowIdKey] || "missing";
                const rowEl = row.getElement();
                
                if (!rowEl) return;
                
                if (displayMode === "tooltip") {
                    // Add tooltip to first cell
                    const firstCell = rowEl.querySelector(".tabulator-cell");
                    if (firstCell) {
                        firstCell.title = `Row ID: ${id}`;
                        firstCell.style.position = "relative";
                        
                        // Add small indicator
                        const indicator = document.createElement("div");
                        indicator.className = "table-monitor-row-id";
                        indicator.style.position = "absolute";
                        indicator.style.top = "0";
                        indicator.style.left = "0";
                        indicator.style.width = "6px";
                        indicator.style.height = "6px";
                        indicator.style.background = data[this.options.rowIdKey] ? "#10b981" : "#ef4444";
                        indicator.style.borderRadius = "50%";
                        firstCell.appendChild(indicator);
                    }
                } else if (displayMode === "visible") {
                    // Create a new cell or label showing the ID
                    const idDisplay = document.createElement("div");
                    idDisplay.className = "table-monitor-row-id";
                    idDisplay.style.position = "absolute";
                    idDisplay.style.left = "2px";
                    idDisplay.style.top = "2px";
                    idDisplay.style.fontSize = "9px";
                    idDisplay.style.padding = "1px 3px";
                    idDisplay.style.background = "rgba(0,0,0,0.7)";
                    idDisplay.style.color = "white";
                    idDisplay.style.borderRadius = "3px";
                    idDisplay.style.zIndex = "100";
                    idDisplay.textContent = id.substr(-8); // Show last 8 chars
                    rowEl.style.position = "relative";
                    rowEl.appendChild(idDisplay);
                }
            });
            
            return true;
        } catch (error) {
            this.reportIssue("VISUALIZATION_ERROR", {
                message: `Error visualizing row IDs: ${error.message}`,
                stack: error.stack
            });
            return false;
        }
    }

    // Static methods for utility functions
    static ensureRowIds(table, rowIdKey = "_row_id") {
        const monitor = new TableMonitor(table, { rowIdKey, debug: false });
        return monitor.fixDuplicateRowIds();
    }

    static quickCheck(table) {
        const monitor = new TableMonitor(table, { debug: false });
        monitor.checkTableHealth();
        return monitor.getHealthMetrics();
    }

    // Create a UI for the monitor
    createUI() {
        const container = document.createElement("div");
        container.className = "table-monitor-ui";
        container.style.position = "fixed";
        container.style.bottom = "10px";
        container.style.right = "10px";
        container.style.backgroundColor = "rgba(0, 0, 0, 0.8)";
        container.style.color = "white";
        container.style.padding = "10px";
        container.style.borderRadius = "5px";
        container.style.zIndex = "10000";
        container.style.fontSize = "12px";
        container.style.fontFamily = "monospace";
        container.style.maxWidth = "300px";
        container.innerHTML = `
            <div style="margin-bottom:8px;font-weight:bold;">Table Monitor</div>
            <div class="monitor-metrics"></div>
            <div style="display:flex;gap:5px;margin-top:10px;">
                <button class="monitor-check-btn">Check</button>
                <button class="monitor-fix-btn">Fix Issues</button>
                <button class="monitor-ids-btn">Show IDs</button>
                <button class="monitor-close-btn">Close</button>
            </div>
        `;
        
        document.body.appendChild(container);
        
        // Add event listeners
        container.querySelector(".monitor-check-btn").addEventListener("click", () => {
            this.checkTableHealth();
            this.updateUI(container);
        });
        
        container.querySelector(".monitor-fix-btn").addEventListener("click", () => {
            this.fixDuplicateRowIds();
            this.fixDomDataMismatch();
            this.checkTableHealth();
            this.updateUI(container);
        });
        
        container.querySelector(".monitor-ids-btn").addEventListener("click", () => {
            const btn = container.querySelector(".monitor-ids-btn");
            if (btn.textContent === "Show IDs") {
                this.visualizeRowIds("visible");
                btn.textContent = "Hide IDs";
            } else {
                document.querySelectorAll(".table-monitor-row-id").forEach(el => el.remove());
                btn.textContent = "Show IDs";
            }
        });
        
        container.querySelector(".monitor-close-btn").addEventListener("click", () => {
            container.remove();
        });
        
        this.updateUI(container);
        
        return container;
    }

    updateUI(container) {
        const metrics = this.getHealthMetrics();
        const metricsEl = container.querySelector(".monitor-metrics");
        
        metricsEl.innerHTML = `
            <div>Status: <span style="color:${metrics.status === 'healthy' ? '#10b981' : '#ef4444'}">${metrics.status}</span></div>
            <div>Rows: ${metrics.rowCount}</div>
            <div>Unique IDs: ${metrics.uniqueRowIds} / ${metrics.rowCount}</div>
            <div>Issues found: ${metrics.issuesFound}</div>
        `;
    }
}