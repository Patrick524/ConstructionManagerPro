/**
 * JavaScript for dashboard charts and data visualization
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard charts
    initDashboardCharts();
    
    // Setup date range selectors
    setupDateRangeSelectors();
    
    // Initialize approval tables
    initApprovalTables();
});

/**
 * Initialize charts on the admin dashboard
 */
function initDashboardCharts() {
    // Job hours chart (pie chart)
    const jobHoursChart = document.getElementById('job-hours-chart');
    if (jobHoursChart) {
        try {
            console.log('Job chart data attributes:', jobHoursChart.dataset);
            let jobLabels = [];
            let jobData = [];
            
            try {
                jobLabels = JSON.parse(jobHoursChart.dataset.labels || '[]');
                console.log('Parsed job labels:', jobLabels);
            } catch (e) {
                console.error('Error parsing job labels:', e);
                jobLabels = [];
            }
            
            try {
                jobData = JSON.parse(jobHoursChart.dataset.values || '[]');
                console.log('Parsed job data:', jobData);
            } catch (e) {
                console.error('Error parsing job data:', e);
                jobData = [];
            }
            
            // Only create chart if we have data
            if (jobLabels.length > 0 && jobData.length > 0) {
                new Chart(jobHoursChart, {
                    type: 'pie',
                    data: {
                        labels: jobLabels,
                        datasets: [{
                            data: jobData,
                            backgroundColor: [
                                '#0d6efd', '#6610f2', '#6f42c1', '#d63384', 
                                '#dc3545', '#fd7e14', '#ffc107', '#198754'
                            ],
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                            },
                            title: {
                                display: true,
                                text: 'Hours by Job'
                            }
                        }
                    }
                });
            } else {
                console.log('No job chart data available');
            }
        } catch (e) {
            console.error('Error initializing job hours chart:', e);
        }
    }
    
    // Trade hours chart (bar chart)
    const tradeHoursChart = document.getElementById('trade-hours-chart');
    if (tradeHoursChart) {
        try {
            console.log('Trade chart data attributes:', tradeHoursChart.dataset);
            let tradeLabels = [];
            let tradeData = [];
            
            try {
                tradeLabels = JSON.parse(tradeHoursChart.dataset.labels || '[]');
                console.log('Parsed trade labels:', tradeLabels);
            } catch (e) {
                console.error('Error parsing trade labels:', e);
                tradeLabels = [];
            }
            
            try {
                tradeData = JSON.parse(tradeHoursChart.dataset.values || '[]');
                console.log('Parsed trade data:', tradeData);
            } catch (e) {
                console.error('Error parsing trade data:', e);
                tradeData = [];
            }
            
            // Only create chart if we have data
            if (tradeLabels.length > 0 && tradeData.length > 0) {
                new Chart(tradeHoursChart, {
                    type: 'bar',
                    data: {
                        labels: tradeLabels,
                        datasets: [{
                            label: 'Hours',
                            data: tradeData,
                            backgroundColor: '#0d6efd',
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            },
                            title: {
                                display: true,
                                text: 'Hours by Trade'
                            }
                        }
                    }
                });
            } else {
                console.log('No trade chart data available');
            }
        } catch (e) {
            console.error('Error initializing trade hours chart:', e);
        }
    }
    
    // Weekly hours trend (line chart)
    const weeklyTrendChart = document.getElementById('weekly-trend-chart');
    if (weeklyTrendChart) {
        const weekLabels = JSON.parse(weeklyTrendChart.dataset.labels || '[]');
        const weekData = JSON.parse(weeklyTrendChart.dataset.values || '[]');
        
        new Chart(weeklyTrendChart, {
            type: 'line',
            data: {
                labels: weekLabels,
                datasets: [{
                    label: 'Total Hours',
                    data: weekData,
                    borderColor: '#0d6efd',
                    tension: 0.1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Weekly Hours Trend'
                    }
                }
            }
        });
    }
}

/**
 * Setup date range selectors for report forms and dashboards
 */
function setupDateRangeSelectors() {
    const dateRangePicker = document.getElementById('date-range-picker');
    
    if (dateRangePicker) {
        // For single week selection
        flatpickr(dateRangePicker, {
            mode: 'single',
            dateFormat: 'Y-m-d',
            altInput: true,
            altFormat: 'F j, Y',
            defaultDate: 'today',
            onClose: function(selectedDates, dateStr) {
                if (selectedDates.length > 0) {
                    // Get the Monday of the selected week
                    const selected = selectedDates[0];
                    const day = selected.getDay();
                    const diff = selected.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is Sunday
                    const monday = new Date(selected.setDate(diff));
                    
                    // Format as YYYY-MM-DD
                    const year = monday.getFullYear();
                    const month = String(monday.getMonth() + 1).padStart(2, '0');
                    const date = String(monday.getDate()).padStart(2, '0');
                    const formattedDate = `${year}-${month}-${date}`;
                    
                    // Update URL and reload
                    const url = new URL(window.location);
                    url.searchParams.set('start_date', formattedDate);
                    window.location.href = url.toString();
                }
            }
        });
    }
    
    // For report date range selection
    const startDatePicker = document.getElementById('start_date');
    const endDatePicker = document.getElementById('end_date');
    
    if (startDatePicker && endDatePicker) {
        // Initialize start date picker
        const startPicker = flatpickr(startDatePicker, {
            dateFormat: 'Y-m-d',
            altInput: true,
            altFormat: 'F j, Y',
            defaultDate: 'today',
            onChange: function(selectedDates) {
                // Update end date minimum
                if (selectedDates.length > 0) {
                    endPicker.set('minDate', selectedDates[0]);
                }
            }
        });
        
        // Initialize end date picker
        const endPicker = flatpickr(endDatePicker, {
            dateFormat: 'Y-m-d',
            altInput: true,
            altFormat: 'F j, Y',
            defaultDate: new Date().fp_incr(6), // Default to a week from start
            minDate: startDatePicker.value || 'today'
        });
    }
}

/**
 * Initialize approval tables with search and sort functionality
 */
function initApprovalTables() {
    const approvalTables = document.querySelectorAll('.approval-table');
    
    approvalTables.forEach(table => {
        const tableId = table.id;
        const searchInput = document.getElementById(`${tableId}-search`);
        
        if (searchInput) {
            searchInput.addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                const rows = table.querySelectorAll('tbody tr');
                
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(searchTerm) ? '' : 'none';
                });
            });
        }
        
        // Make table headers sortable
        const headers = table.querySelectorAll('th[data-sort]');
        
        headers.forEach(header => {
            header.addEventListener('click', function() {
                const sortKey = this.dataset.sort;
                const sortDirection = this.dataset.sortDir === 'asc' ? 'desc' : 'asc';
                
                // Update all headers to remove sorting indicators
                headers.forEach(h => {
                    h.dataset.sortDir = '';
                    h.querySelector('i')?.remove();
                });
                
                // Add sorting indicator to this header
                this.dataset.sortDir = sortDirection;
                const icon = document.createElement('i');
                icon.className = `ms-1 fa fa-sort-${sortDirection === 'asc' ? 'up' : 'down'}`;
                this.appendChild(icon);
                
                // Sort the table
                sortTable(table, sortKey, sortDirection);
            });
        });
    });
}

/**
 * Sort a table by the specified column and direction
 */
function sortTable(table, sortKey, sortDirection) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Sort the rows
    rows.sort((a, b) => {
        const aValue = a.querySelector(`td[data-${sortKey}]`)?.dataset[sortKey] || '';
        const bValue = b.querySelector(`td[data-${sortKey}]`)?.dataset[sortKey] || '';
        
        // Determine if values are numbers
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        
        // Compare based on type
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return sortDirection === 'asc' ? aNum - bNum : bNum - aNum;
        } else {
            return sortDirection === 'asc' ? 
                aValue.localeCompare(bValue) : 
                bValue.localeCompare(aValue);
        }
    });
    
    // Re-append rows in sorted order
    rows.forEach(row => tbody.appendChild(row));
}
