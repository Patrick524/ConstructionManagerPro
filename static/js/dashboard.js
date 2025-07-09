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
    
    // Initialize inactive jobs filter
    initInactiveJobsFilter();
});

/**
 * Initialize charts on the admin dashboard
 */
function initDashboardCharts() {
    // Define default colors for charts
    const colors = [
        '#0d6efd', '#6610f2', '#6f42c1', '#d63384', 
        '#dc3545', '#fd7e14', '#ffc107', '#198754'
    ];

    // Job hours chart (pie chart)
    const jobHoursChart = document.getElementById('job-hours-chart');
    if (jobHoursChart) {
        try {
            // Directly access server data
            const chartData = JSON.parse(document.getElementById('job-hours-data').textContent || '[]');
            console.log('Job chart data:', chartData);
            
            if (chartData && chartData.length > 0) {
                const labels = chartData.map(item => item[0]);
                const values = chartData.map(item => item[1]);
                
                new Chart(jobHoursChart, {
                    type: 'pie',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: colors,
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
            // Directly access server data
            const chartData = JSON.parse(document.getElementById('trade-hours-data').textContent || '[]');
            console.log('Trade chart data:', chartData);
            
            if (chartData && chartData.length > 0) {
                const labels = chartData.map(item => item[0]);
                const values = chartData.map(item => item[1]);
                
                new Chart(tradeHoursChart, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Hours',
                            data: values,
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
        // Get current week start from the page data
        const currentWeekElement = document.querySelector('[data-current-week-start]');
        const currentWeekStart = currentWeekElement ? currentWeekElement.dataset.currentWeekStart : null;
        
        // For single week selection
        flatpickr(dateRangePicker, {
            mode: 'single',
            dateFormat: 'Y-m-d',
            altInput: true,
            altFormat: 'F j, Y',
            defaultDate: currentWeekStart || 'today',
            onClose: function(selectedDates, dateStr) {
                if (selectedDates.length > 0) {
                    // Get the Monday of the selected week
                    const selected = selectedDates[0];
                    const day = selected.getDay();
                    const diff = selected.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is Sunday
                    const monday = new Date(selected.setDate(diff));
                    
                    // Format as MM/DD/YYYY for foreman dashboard
                    const month = String(monday.getMonth() + 1).padStart(2, '0');
                    const date = String(monday.getDate()).padStart(2, '0');
                    const year = monday.getFullYear();
                    const formattedDate = `${month}/${date}/${year}`;
                    
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

/**
 * Initialize the inactive jobs filter toggle
 */
function initInactiveJobsFilter() {
    const hideInactiveToggle = document.getElementById('hideInactiveJobs');
    
    if (hideInactiveToggle) {
        // Apply initial state (toggle is checked by default)
        toggleInactiveJobs(hideInactiveToggle.checked);
        
        // Add event listener for toggle changes
        hideInactiveToggle.addEventListener('change', function() {
            toggleInactiveJobs(this.checked);
        });
    }
}

/**
 * Toggle visibility of inactive job cards
 */
function toggleInactiveJobs(hideInactive) {
    const emptyJobCards = document.querySelectorAll('.card.empty-job');
    
    emptyJobCards.forEach(card => {
        if (hideInactive) {
            card.style.display = 'none';
        } else {
            card.style.display = 'block';
        }
    });
}
