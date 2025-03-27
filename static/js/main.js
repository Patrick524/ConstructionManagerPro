/**
 * Main JavaScript for Construction Timesheet application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize date pickers for all date input fields
    initDatePickers();
    
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Handle high contrast mode toggle
    setupHighContrastMode();
    
    // Setup week navigation for screens with date ranges
    setupWeekNavigation();
});

/**
 * Initialize flatpickr date pickers
 */
function initDatePickers() {
    const dateInputs = document.querySelectorAll('input[type="date"]');
    
    dateInputs.forEach(input => {
        flatpickr(input, {
            dateFormat: "Y-m-d",
            allowInput: true,
            altInput: true,
            altFormat: "F j, Y",
            // Better mobile support
            disableMobile: false
        });
    });
}

/**
 * Handle high contrast mode toggle for outdoor visibility
 */
function setupHighContrastMode() {
    const highContrastToggle = document.getElementById('high-contrast-toggle');
    
    if (highContrastToggle) {
        // Check if user preference is stored
        const highContrastEnabled = localStorage.getItem('highContrastMode') === 'true';
        
        // Apply high contrast mode if enabled
        if (highContrastEnabled) {
            document.body.classList.add('high-contrast');
            highContrastToggle.checked = true;
        }
        
        // Listen for toggle changes
        highContrastToggle.addEventListener('change', function() {
            if (this.checked) {
                document.body.classList.add('high-contrast');
                localStorage.setItem('highContrastMode', 'true');
            } else {
                document.body.classList.remove('high-contrast');
                localStorage.setItem('highContrastMode', 'false');
            }
        });
    }
}

/**
 * Setup week navigation for screens with date ranges
 */
function setupWeekNavigation() {
    const prevWeekBtn = document.getElementById('prev-week');
    const nextWeekBtn = document.getElementById('next-week');
    const currentWeekBtn = document.getElementById('current-week');
    
    if (prevWeekBtn && nextWeekBtn && currentWeekBtn) {
        // Get current start date from URL or data attribute
        const urlParams = new URLSearchParams(window.location.search);
        let startDate = urlParams.get('start_date');
        
        if (!startDate) {
            const dateElement = document.querySelector('[data-current-week-start]');
            startDate = dateElement ? dateElement.dataset.currentWeekStart : null;
        }
        
        if (startDate) {
            // Set up previous week button
            prevWeekBtn.addEventListener('click', function() {
                navigateToWeek(startDate, -7);
            });
            
            // Set up next week button
            nextWeekBtn.addEventListener('click', function() {
                navigateToWeek(startDate, 7);
            });
            
            // Set up current week button
            currentWeekBtn.addEventListener('click', function() {
                window.location.href = window.location.pathname;
            });
        }
    }
}

/**
 * Navigate to a different week based on offset from start date
 */
function navigateToWeek(startDate, dayOffset) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + dayOffset);
    
    // Convert to YYYY-MM-DD format
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const newStartDate = `${year}-${month}-${day}`;
    
    // Update URL and reload
    const url = new URL(window.location);
    url.searchParams.set('start_date', newStartDate);
    window.location.href = url.toString();
}

/**
 * Format a date as YYYY-MM-DD
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * Format a date for display (Month Day, Year)
 */
function formatDisplayDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        month: 'long', 
        day: 'numeric', 
        year: 'numeric' 
    });
}

/**
 * Show loading spinner
 */
function showLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `
            <div class="d-flex justify-content-center align-items-center p-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
    }
}

/**
 * Handle API errors
 */
function handleApiError(error, containerId) {
    console.error('API Error:', error);
    
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <h4 class="alert-heading">Error!</h4>
                <p>There was an error loading the data. Please try again or contact support if the problem persists.</p>
                <hr>
                <p class="mb-0">Details: ${error.message || 'Unknown error'}</p>
            </div>
        `;
    }
}
