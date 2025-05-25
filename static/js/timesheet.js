/**
 * JavaScript for Worker Timesheet functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dynamic labor activity fields
    setupLaborActivityFields();
    
    // Handle job selection changes
    setupJobSelection();
    
    // Handle date changes to reload existing entries
    setupDateSelection();
    
    // Setup add/remove activity buttons
    setupActivityButtons();
    
    // Setup quick hour selection buttons
    setupHourButtons();
});

/**
 * Initialize dynamic labor activity fields
 */
function setupLaborActivityFields() {
    // Count how many labor activity fields we already have (could be pre-populated)
    const activityContainer = document.getElementById('labor-activities-container');
    if (activityContainer) {
        let activityCount = activityContainer.querySelectorAll('.activity-entry').length;
        
        // Store the count for use with add/remove functions
        activityContainer.dataset.activityCount = activityCount || 1;
    }
}

/**
 * Setup job selection change handler to load appropriate labor activities
 */
function setupJobSelection() {
    const jobSelect = document.getElementById('job_id');
    
    if (jobSelect) {
        jobSelect.addEventListener('change', function() {
            const jobId = this.value;
            
            if (jobId) {
                // Fetch labor activities for this job
                fetch(`/api/labor_activities/${jobId}`)
                    .then(response => response.json())
                    .then(activities => {
                        // Update all labor activity select fields
                        updateLaborActivityOptions(activities);
                        
                        // Check if there are existing entries for this job/date
                        const dateInput = document.getElementById('date');
                        if (dateInput && dateInput.value) {
                            loadExistingEntries(jobId, dateInput.value);
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching labor activities:', error);
                    });
            }
        });
        
        // Trigger change event if a job is already selected
        if (jobSelect.value) {
            jobSelect.dispatchEvent(new Event('change'));
        }
    }
}

/**
 * Setup date selection change handler
 */
function setupDateSelection() {
    const dateInput = document.getElementById('date');
    const jobSelect = document.getElementById('job_id');
    
    if (dateInput && jobSelect) {
        dateInput.addEventListener('change', function() {
            const jobId = jobSelect.value;
            const date = this.value;
            
            if (jobId && date) {
                loadExistingEntries(jobId, date);
            }
        });
        
        // Trigger change event if a date is already selected
        if (dateInput.value && jobSelect.value) {
            dateInput.dispatchEvent(new Event('change'));
        }
    }
}

/**
 * Load existing time entries for a job and date
 */
function loadExistingEntries(jobId, date) {
    fetch(`/api/time_entries/${date}/${jobId}`)
        .then(response => response.json())
        .then(entries => {
            if (entries && entries.length > 0) {
                // Reset activity fields
                resetActivityFields();
                
                // Add fields for each entry
                entries.forEach((entry, index) => {
                    if (index === 0) {
                        // Update the first activity field
                        document.getElementById('labor_activity_1').value = entry.labor_activity_id;
                        document.getElementById('hours_1').value = entry.hours;
                    } else {
                        // Add new activity fields for additional entries
                        addActivityField(entry.labor_activity_id, entry.hours);
                    }
                });
                
                // Add notes if available (from first entry since notes are shared)
                const notesField = document.getElementById('notes');
                if (notesField && entries[0].notes) {
                    notesField.value = entries[0].notes;
                }
            } else {
                // Reset all fields if no entries found
                resetActivityFields();
                
                const notesField = document.getElementById('notes');
                if (notesField) {
                    notesField.value = '';
                }
            }
        })
        .catch(error => {
            console.error('Error loading existing entries:', error);
        });
}

/**
 * Update all labor activity select fields with new options
 */
function updateLaborActivityOptions(activities) {
    const activitySelects = document.querySelectorAll('[id^="labor_activity_"]');
    
    activitySelects.forEach(select => {
        // Store current selection if possible
        const currentValue = select.value;
        
        // Clear existing options
        select.innerHTML = '';
        
        // Add a blank option
        const blankOption = document.createElement('option');
        blankOption.value = '';
        blankOption.textContent = '-- Select Activity --';
        select.appendChild(blankOption);
        
        // Add new options
        activities.forEach(activity => {
            const option = document.createElement('option');
            option.value = activity.id;
            option.textContent = activity.name;
            select.appendChild(option);
        });
        
        // Restore previous selection if it still exists
        if (currentValue) {
            const exists = Array.from(select.options).some(option => option.value === currentValue);
            if (exists) {
                select.value = currentValue;
            }
        }
    });
}

/**
 * Setup add/remove activity buttons
 */
function setupActivityButtons() {
    const addButton = document.getElementById('add-activity');
    
    if (addButton) {
        addButton.addEventListener('click', function(e) {
            e.preventDefault();
            addActivityField();
        });
    }
    
    // Set up event delegation for remove buttons
    const activitiesContainer = document.getElementById('labor-activities-container');
    if (activitiesContainer) {
        activitiesContainer.addEventListener('click', function(e) {
            if (e.target && e.target.classList.contains('remove-activity')) {
                e.preventDefault();
                removeActivityField(e.target);
            }
        });
    }
}

/**
 * Add a new labor activity field
 */
function addActivityField(activityId = '', hours = '0') {
    const container = document.getElementById('labor-activities-container');
    if (!container) return;
    
    // Get current count and increment
    let count = parseInt(container.dataset.activityCount) || 1;
    count++;
    container.dataset.activityCount = count;
    
    // Create new activity field HTML
    const newField = document.createElement('div');
    newField.className = 'activity-entry';
    newField.id = `activity-entry-${count}`;
    
    // Get existing labor activity options from the first select field
    const laborActivityOptions = document.getElementById('labor_activity_1');
    
    let optionsHtml = '';
    if (laborActivityOptions) {
        Array.from(laborActivityOptions.options).forEach(option => {
            const selected = option.value === activityId ? 'selected' : '';
            optionsHtml += `<option value="${option.value}" ${selected}>${option.textContent}</option>`;
        });
    }
    
    newField.innerHTML = `
        <div class="row">
            <div class="col-md-8 mb-3">
                <label for="labor_activity_${count}" class="form-label">Labor Activity</label>
                <select class="form-select" id="labor_activity_${count}" name="labor_activity_${count}">
                    ${optionsHtml}
                </select>
            </div>
            <div class="col-md-4 mb-3">
                <label for="hours_${count}" class="form-label">Hours</label>
                <!-- Quick Hour Selection Buttons -->
                <div class="mb-2">
                    <div class="btn-group w-100" role="group" aria-label="Quick hour selection">
                        <button type="button" class="btn btn-outline-primary btn-sm hour-btn" data-hours="4">4h</button>
                        <button type="button" class="btn btn-outline-primary btn-sm hour-btn" data-hours="8">8h</button>
                        <button type="button" class="btn btn-outline-primary btn-sm hour-btn" data-hours="10">10h</button>
                        <button type="button" class="btn btn-outline-primary btn-sm hour-btn" data-hours="12">12h</button>
                    </div>
                </div>
                <input type="number" class="form-control" id="hours_${count}" name="hours_${count}" 
                       min="0" max="12" step="0.5" value="${hours}">
            </div>
        </div>
        <button type="button" class="btn btn-sm btn-outline-danger remove-activity">
            <i class="fa fa-times"></i> Remove Activity
        </button>
    `;
    
    // Add the new field to the container
    container.appendChild(newField);
}

/**
 * Remove a labor activity field
 */
function removeActivityField(button) {
    // Find the parent activity entry
    const entry = button.closest('.activity-entry');
    if (entry && entry.id !== 'activity-entry-1') {
        entry.remove();
    }
}

/**
 * Reset all activity fields to default state
 */
function resetActivityFields() {
    const container = document.getElementById('labor-activities-container');
    if (!container) return;
    
    // Keep only the first activity field
    const entries = container.querySelectorAll('.activity-entry');
    for (let i = 1; i < entries.length; i++) {
        entries[i].remove();
    }
    
    // Reset the first activity field
    const laborActivitySelect = document.getElementById('labor_activity_1');
    const hoursInput = document.getElementById('hours_1');
    
    if (laborActivitySelect) laborActivitySelect.value = '';
    if (hoursInput) hoursInput.value = '0'; // Set default value to 0 instead of empty string
    
    // Reset activity count
    container.dataset.activityCount = 1;
}

/**
 * Setup quick hour selection buttons
 */
function setupHourButtons() {
    // Set up event delegation for hour buttons
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('hour-btn')) {
            e.preventDefault();
            
            // Get the hours value from the button
            const hours = e.target.getAttribute('data-hours');
            
            // Find the closest hours input field
            const hoursInput = e.target.closest('.col-md-4').querySelector('input[type="number"]');
            
            if (hoursInput && hours) {
                // Set the value
                hoursInput.value = hours;
                
                // Remove active state from other buttons in the same group
                const buttonGroup = e.target.closest('.btn-group');
                if (buttonGroup) {
                    buttonGroup.querySelectorAll('.hour-btn').forEach(btn => {
                        btn.classList.remove('btn-primary');
                        btn.classList.add('btn-outline-primary');
                    });
                }
                
                // Add active state to clicked button
                e.target.classList.remove('btn-outline-primary');
                e.target.classList.add('btn-primary');
                
                // Trigger change event on input for any listeners
                hoursInput.dispatchEvent(new Event('change', { bubbles: true }));
                
                // Trigger input event for immediate feedback
                hoursInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    });
    
    // Also handle when hour input is changed manually - update button states
    document.addEventListener('input', function(e) {
        if (e.target && e.target.type === 'number' && e.target.name && e.target.name.startsWith('hours_')) {
            const value = parseFloat(e.target.value);
            const buttonGroup = e.target.closest('.col-md-4').querySelector('.btn-group');
            
            if (buttonGroup) {
                // Reset all buttons to outline state
                buttonGroup.querySelectorAll('.hour-btn').forEach(btn => {
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-primary');
                });
                
                // Highlight button if value matches
                const matchingButton = buttonGroup.querySelector(`[data-hours="${value}"]`);
                if (matchingButton) {
                    matchingButton.classList.remove('btn-outline-primary');
                    matchingButton.classList.add('btn-primary');
                }
            }
        }
    });
}
