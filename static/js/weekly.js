// weekly.js - JavaScript for the weekly timesheet view

document.addEventListener('DOMContentLoaded', function() {
    initializeWeeklyTimesheet();
});

function initializeWeeklyTimesheet() {
    // Connect event listeners to all hour inputs
    connectHourInputs();
    
    // Initialize "Add Job" button if present
    const addJobBtn = document.getElementById('addJobRow');
    if (addJobBtn) {
        addJobBtn.addEventListener('click', addNewJobRow);
    }
    
    // Calculate initial totals
    recalculateAllTotals();
}

function connectHourInputs() {
    // Find all hour input fields and attach change listeners
    const hourInputs = document.querySelectorAll('.hour-input');
    hourInputs.forEach(input => {
        input.addEventListener('change', function() {
            validateHourInput(this);
            recalculateAllTotals();
        });
        input.addEventListener('keyup', function() {
            validateHourInput(this);
            recalculateAllTotals();
        });
    });
}

function validateHourInput(inputField) {
    const hours = parseFloat(inputField.value) || 0;
    const row = inputField.closest('tr');
    
    // Reset validation state
    inputField.classList.remove('is-invalid');
    
    // Validate hours (between 0 and 24)
    if (hours < 0 || hours > 24) {
        inputField.classList.add('is-invalid');
        // Add error message if not already present
        let errorDiv = inputField.nextElementSibling;
        if (!errorDiv || !errorDiv.classList.contains('invalid-feedback')) {
            errorDiv = document.createElement('div');
            errorDiv.classList.add('invalid-feedback');
            errorDiv.textContent = 'Hours must be between 0 and 24';
            inputField.parentNode.appendChild(errorDiv);
        }
    }
    
    return hours;
}

function recalculateAllTotals() {
    // Calculate day totals
    const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    let weekTotal = 0;
    
    days.forEach(day => {
        const dayTotal = calculateDayTotal(day);
        weekTotal += dayTotal;
        updateDayTotal(day, dayTotal);
    });
    
    // Calculate row totals for each job
    const jobRows = document.querySelectorAll('.job-row');
    jobRows.forEach(row => {
        calculateJobRowTotal(row);
    });
    
    // Update week total
    updateWeekTotal(weekTotal);
    
    // Check for any validation issues
    checkForValidationIssues();
}

function calculateDayTotal(day) {
    const dayInputs = document.querySelectorAll(`.${day}-hours`);
    let total = 0;
    
    dayInputs.forEach(input => {
        const hours = parseFloat(input.value) || 0;
        total += hours;
    });
    
    return total;
}

function updateDayTotal(day, total) {
    const dayTotalElement = document.getElementById(`${day}Total`);
    if (dayTotalElement) {
        dayTotalElement.textContent = total.toFixed(1);
        
        // Highlight if over 24 hours
        if (total > 24) {
            dayTotalElement.classList.add('text-danger', 'fw-bold');
        } else {
            dayTotalElement.classList.remove('text-danger', 'fw-bold');
        }
    }
}

function calculateJobRowTotal(row) {
    const hourInputs = row.querySelectorAll('.hour-input');
    let rowTotal = 0;
    
    hourInputs.forEach(input => {
        const hours = parseFloat(input.value) || 0;
        rowTotal += hours;
    });
    
    // Update row total
    const totalCell = row.querySelector('.row-total');
    if (totalCell) {
        totalCell.textContent = rowTotal.toFixed(1);
    }
    
    return rowTotal;
}

function updateWeekTotal(total) {
    const weekTotalElement = document.getElementById('totalHours');
    if (weekTotalElement) {
        weekTotalElement.textContent = total.toFixed(1);
        
        // Highlight if over 168 hours (7 days * 24 hours)
        if (total > 168) {
            weekTotalElement.classList.add('text-danger', 'fw-bold');
        } else {
            weekTotalElement.classList.remove('text-danger', 'fw-bold');
        }
    }
}

function checkForValidationIssues() {
    const invalidInputs = document.querySelectorAll('.hour-input.is-invalid');
    const submitButton = document.querySelector('button[type="submit"]');
    
    if (invalidInputs.length > 0) {
        // Disable submit button if any invalid inputs
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.title = 'Please fix validation errors before submitting';
        }
    } else {
        // Enable submit button if all inputs are valid
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.title = '';
        }
    }
}

function addNewJobRow() {
    const template = document.getElementById('jobRowTemplate');
    if (!template) return;
    
    // Clone the template
    const clone = template.content.cloneNode(true);
    
    // Get a new unique row ID
    const rowId = Date.now();
    
    // Update IDs and names in the new row
    const selects = clone.querySelectorAll('select');
    selects.forEach(select => {
        const originalName = select.name;
        select.name = originalName.replace('template', rowId);
        select.id = select.id.replace('template', rowId);
    });
    
    const inputs = clone.querySelectorAll('input');
    inputs.forEach(input => {
        const originalName = input.name;
        input.name = originalName.replace('template', rowId);
        input.id = input.id.replace('template', rowId);
        input.value = '0.0';
    });
    
    // Add event listeners to the new inputs
    const newInputs = clone.querySelectorAll('.hour-input');
    newInputs.forEach(input => {
        input.addEventListener('change', function() {
            validateHourInput(this);
            recalculateAllTotals();
        });
        input.addEventListener('keyup', function() {
            validateHourInput(this);
            recalculateAllTotals();
        });
    });
    
    // Add the new row to the table
    const tbody = document.querySelector('#weeklyTimesheetTable tbody');
    if (tbody) {
        tbody.appendChild(clone);
        recalculateAllTotals();
    }
}