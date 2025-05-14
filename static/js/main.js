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
    // Look for the week navigation elements
    const prevWeekBtn = document.getElementById('prev-week');
    const nextWeekBtn = document.getElementById('next-week');
    const currentWeekBtn = document.getElementById('current-week');
    
    // Highlight the current week button if we're on the current week
    function updateCurrentWeekHighlight() {
        const today = new Date();
        const dayOfWeek = today.getDay();
        const daysToSubtract = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // If Sunday (0), go back 6 days, otherwise go back (dayOfWeek - 1) days
        const thisMonday = new Date(today);
        thisMonday.setDate(today.getDate() - daysToSubtract);
        
        // Format as YYYY-MM-DD for comparison
        const thisMondayStr = thisMonday.toISOString().slice(0, 10);
        
        // Get the displayed week start date from the alert element
        const weekAlert = document.querySelector('.alert[data-current-week-start]');
        if (weekAlert && weekAlert.dataset.currentWeekStart) {
            // If the displayed week is the current week, highlight the Current Week button
            if (weekAlert.dataset.currentWeekStart === thisMondayStr) {
                currentWeekBtn.classList.add('btn-primary');
                currentWeekBtn.classList.remove('btn-outline-primary');
            } else {
                currentWeekBtn.classList.remove('btn-primary');
                currentWeekBtn.classList.add('btn-outline-primary');
            }
        }
    }
    
    if (prevWeekBtn && nextWeekBtn && currentWeekBtn) {
        // Extract the start date from the alert - this contains the Monday set by the backend
        const weekAlert = document.querySelector('.alert[data-current-week-start]');
        
        if (weekAlert && weekAlert.dataset.currentWeekStart) {
            // Always get a fresh date from the DOM when needed
            function getCurrentWeekStart() {
                return new Date(weekAlert.dataset.currentWeekStart);
            }
            
            console.log(`Week navigation initialized with start date: ${weekAlert.dataset.currentWeekStart}`);
            
            // Update the current week highlight
            updateCurrentWeekHighlight();
            
            // Set up previous week button
            prevWeekBtn.addEventListener('click', function(e) {
                e.preventDefault();
                const currentWeekStart = getCurrentWeekStart();
                const prevWeek = new Date(currentWeekStart);
                prevWeek.setDate(prevWeek.getDate() - 7);
                
                // Format as YYYY-MM-DD
                const prevWeekStr = prevWeek.toISOString().slice(0, 10);
                
                console.log(`Previous Week: ${currentWeekStart.toISOString().slice(0, 10)} → ${prevWeekStr}`);
                
                // Update URL and reload
                const url = new URL(window.location);
                url.searchParams.set('start_date', prevWeekStr);
                window.location.href = url.toString();
            });
            
            // Set up next week button
            nextWeekBtn.addEventListener('click', function(e) {
                e.preventDefault();
                const currentWeekStart = getCurrentWeekStart();
                const nextWeek = new Date(currentWeekStart);
                nextWeek.setDate(nextWeek.getDate() + 7);
                
                // Format as YYYY-MM-DD
                const nextWeekStr = nextWeek.toISOString().slice(0, 10);
                
                console.log(`Next Week: ${currentWeekStart.toISOString().slice(0, 10)} → ${nextWeekStr}`);
                
                // Update URL and reload
                const url = new URL(window.location);
                url.searchParams.set('start_date', nextWeekStr);
                window.location.href = url.toString();
            });
            
            // Set up current week button - for the current week, we don't include any date params
            // This will let the backend use its default logic to calculate the current week
            currentWeekBtn.addEventListener('click', function(e) {
                e.preventDefault();
                // Remove any start_date from the URL if present, to let backend use its default logic
                const url = new URL(window.location);
                url.searchParams.delete('start_date');
                url.searchParams.delete('week_offset');
                
                // Log what we're doing
                console.log(`Current Week: Removing date parameters to let backend calculate current week`);
                
                // Update URL and reload, which will use backend's current week calculation
                window.location.href = url.toString();
            });
        } else {
            console.error("Week alert element with data-current-week-start not found. Week navigation may not work correctly.");
        }
    }
}

/**
 * Get the Monday of a given date
 * @param {Date} date - The date to get the Monday for
 * @returns {Date} - The Monday of the week containing the given date
 */
function getMondayOfWeek(date) {
    const dayOfWeek = date.getDay();
    const daysToSubtract = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // If Sunday (0), go back 6 days, otherwise go back (dayOfWeek - 1) days
    const result = new Date(date);
    result.setDate(date.getDate() - daysToSubtract);
    return result;
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

/* Hamburger menu function removed to use native Bootstrap behavior */
