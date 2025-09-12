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
    
    // Setup form submission tracking for smart sorting
    setupFormSubmissionTracking();
    
    // Setup last used job defaulting
    setupLastUsedJobDefaulting();
});

/**
 * Check if we're in edit mode (editing an existing entry)
 */
function isEditMode() {
    // Check if the page URL contains '/edit/' or if there's an entry_to_edit variable
    const editMode = window.location.pathname.includes('/edit/') || 
           (typeof entry_to_edit !== 'undefined' && entry_to_edit !== null);
    console.log(`Edit mode check: URL contains /edit/: ${window.location.pathname.includes('/edit/')}, entry_to_edit defined: ${typeof entry_to_edit !== 'undefined' && entry_to_edit !== null}, result: ${editMode}`);
    return editMode;
}

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
            console.log('Job selection changed:', { 
                jobId: jobId, 
                jobIdType: typeof jobId, 
                selectedText: this.options[this.selectedIndex].text 
            });
            
            if (jobId) {
                // Fetch labor activities for this job
                console.log(`Fetching activities from: /api/labor_activities/${jobId}`);
                fetch(`/api/labor_activities/${jobId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            // Show error message to user
                            alert(data.error);
                            // Clear activity options
                            updateLaborActivityOptions([]);
                        } else {
                            // Update all labor activity select fields with trade groups
                            updateLaborActivityOptions(data.trade_groups || data.activities || data);
                            
                            // Check if there are existing entries for this job/date
                            const dateInput = document.getElementById('date');
                            if (dateInput && dateInput.value) {
                                loadExistingEntries(jobId, dateInput.value);
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching labor activities:', error);
                    });
            }
        });
        
        // Trigger change event if a job is already selected, but only if we're not in edit mode
        if (jobSelect.value && !isEditMode()) {
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
            
            // Skip loading existing entries if we're in edit mode
            if (jobId && date && !isEditMode()) {
                loadExistingEntries(jobId, date);
            }
        });
        
        // Trigger change event if a date is already selected, but only if we're not in edit mode
        if (dateInput.value && jobSelect.value && !isEditMode()) {
            dateInput.dispatchEvent(new Event('change'));
        }
    }
}

/**
 * Load existing time entries for a job and date
 */
function loadExistingEntries(jobId, date) {
    console.log(`loadExistingEntries called with jobId: ${jobId}, date: ${date}, isEditMode: ${isEditMode()}`);
    
    if (isEditMode()) {
        console.log('Skipping loadExistingEntries because we are in edit mode');
        return;
    }
    
    fetch(`/api/time_entries/${date}/${jobId}`)
        .then(response => response.json())
        .then(entries => {
            console.log(`Loaded ${entries.length} entries from API:`, entries);
            if (entries && entries.length > 0) {
                // Reset activity fields
                resetActivityFields();
                
                // Add fields for each entry
                entries.forEach((entry, index) => {
                    if (index === 0) {
                        // Update the first activity field
                        document.getElementById('labor_activity_1').value = entry.labor_activity_id;
                        document.getElementById('hours_1').value = entry.hours;
                        console.log(`Set hours_1 to ${entry.hours} from API entry`);
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
 * Update all labor activity select fields with new options using smart sorting and trade grouping
 */
function updateLaborActivityOptions(tradeGroupsOrActivities) {
    const activitySelects = document.querySelectorAll('[id^="labor_activity_"], #labor_activity_id');
    const jobSelect = document.getElementById('job_id');
    const currentJobId = jobSelect ? jobSelect.value : null;
    
    activitySelects.forEach(select => {
        // Store current selection if possible
        const currentValue = select.value;
        
        // Clear existing options
        select.innerHTML = '';
        
        let firstActivityId = null;
        
        // Check if we have trade groups (new format) or just activities (fallback)
        if (Array.isArray(tradeGroupsOrActivities) && tradeGroupsOrActivities.length > 0 && tradeGroupsOrActivities[0].trade_name) {
            // New grouped format - create optgroups
            tradeGroupsOrActivities.forEach(tradeGroup => {
                const optgroup = document.createElement('optgroup');
                optgroup.label = tradeGroup.trade_name;
                
                // Activities within each trade are already sorted alphabetically by the API
                // Keep alphabetical order - don't apply usage-based smart sorting within trade groups
                const sortedActivities = tradeGroup.activities.sort((a, b) => a.name.localeCompare(b.name));
                
                sortedActivities.forEach(activity => {
                    const option = document.createElement('option');
                    option.value = activity.id;
                    option.textContent = activity.name;
                    optgroup.appendChild(option);
                    
                    // Store first activity for auto-selection
                    if (!firstActivityId) {
                        firstActivityId = activity.id;
                    }
                });
                
                select.appendChild(optgroup);
            });
        } else {
            // Fallback for old format or error cases - treat as flat list
            const activities = Array.isArray(tradeGroupsOrActivities) ? tradeGroupsOrActivities : [];
            const sortedActivities = smartSortActivities(activities, currentJobId);
            
            sortedActivities.forEach(activity => {
                const option = document.createElement('option');
                option.value = activity.id;
                option.textContent = activity.name;
                select.appendChild(option);
                
                // Store first activity for auto-selection
                if (!firstActivityId) {
                    firstActivityId = activity.id;
                }
            });
        }
        
        // Auto-select the first activity (most frequently used or first alphabetically)
        if (!currentValue && firstActivityId) {
            select.value = firstActivityId;
        } else if (currentValue) {
            // Restore previous selection if it still exists
            const exists = Array.from(select.options).some(option => option.value === currentValue);
            if (exists) {
                select.value = currentValue;
            } else if (firstActivityId) {
                // If previous selection doesn't exist, fall back to first activity
                select.value = firstActivityId;
            }
        }
    });
}

/**
 * Smart sort activities by usage frequency for a specific job
 */
function smartSortActivities(activities, jobId) {
    if (!jobId) {
        // No job selected, return alphabetical sort
        return activities.sort((a, b) => a.name.localeCompare(b.name));
    }
    
    // Get usage counts for each activity with this job
    const activitiesWithUsage = activities.map(activity => ({
        ...activity,
        usageCount: getActivityUsageCount(jobId, activity.name)
    }));
    
    // Sort by usage count (highest first), then alphabetically
    return activitiesWithUsage.sort((a, b) => {
        if (a.usageCount !== b.usageCount) {
            return b.usageCount - a.usageCount; // Higher usage first
        }
        return a.name.localeCompare(b.name); // Alphabetical fallback
    });
}

/**
 * Get usage count for a specific job + activity combination
 */
function getActivityUsageCount(jobId, activityName) {
    const key = `usage_${jobId}_${activityName}`;
    const count = localStorage.getItem(key);
    return count ? parseInt(count, 10) : 0;
}

/**
 * Increment usage count for a job + activity combination
 */
function incrementActivityUsage(jobId, activityName) {
    const key = `usage_${jobId}_${activityName}`;
    const currentCount = getActivityUsageCount(jobId, activityName);
    localStorage.setItem(key, (currentCount + 1).toString());
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
        // Handle both optgroups and regular options
        Array.from(laborActivityOptions.children).forEach(child => {
            if (child.tagName === 'OPTGROUP') {
                // Copy optgroup structure
                optionsHtml += `<optgroup label="${child.label}">`;
                Array.from(child.options).forEach(option => {
                    if (option.value && option.value !== '') {
                        const selected = option.value === activityId ? 'selected' : '';
                        optionsHtml += `<option value="${option.value}" ${selected}>${option.textContent}</option>`;
                    }
                });
                optionsHtml += `</optgroup>`;
            } else if (child.tagName === 'OPTION') {
                // Handle regular options (fallback)
                if (child.value && child.value !== '') {
                    const selected = child.value === activityId ? 'selected' : '';
                    optionsHtml += `<option value="${child.value}" ${selected}>${child.textContent}</option>`;
                }
            }
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
    
    // Auto-select the first activity option (since we removed blank options)
    if (laborActivitySelect && laborActivitySelect.options.length > 0) {
        laborActivitySelect.value = laborActivitySelect.options[0].value;
    }
    if (hoursInput && !isEditMode()) {
        hoursInput.value = '0'; // Set default value to 0 instead of empty string
    }
    
    // Reset activity count
    container.dataset.activityCount = 1;
}

/**
 * Setup form submission tracking for smart activity sorting
 */
function setupFormSubmissionTracking() {
    const form = document.querySelector('form');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        // Track usage data before form submission
        const jobSelect = document.getElementById('job_id');
        const jobId = jobSelect ? jobSelect.value : null;
        
        if (!jobId) return; // No job selected, skip tracking
        
        // Find all activity fields and track their usage
        const activitySelects = document.querySelectorAll('[id^="labor_activity_"]');
        activitySelects.forEach(select => {
            const activityId = select.value;
            const activityName = select.selectedOptions[0]?.textContent;
            
            // Only track if an activity is selected and has a name
            if (activityId && activityName && activityName !== '-- Select Activity --') {
                // Get corresponding hours field to check if there are actual hours
                const fieldNumber = select.id.replace('labor_activity_', '');
                const hoursField = document.getElementById(`hours_${fieldNumber}`);
                const hours = hoursField ? parseFloat(hoursField.value) || 0 : 0;
                
                // Only track usage if hours > 0 (actual work was done)
                if (hours > 0) {
                    incrementActivityUsage(jobId, activityName);
                    console.log(`Tracked usage: Job ${jobId} + Activity "${activityName}" (${hours} hours)`);
                }
            }
        });
        
        // Store the last used job for next time
        setLastUsedJob(jobId);
    });
}

/**
 * Setup last used job defaulting
 */
function setupLastUsedJobDefaulting() {
    const jobSelect = document.getElementById('job_id');
    if (!jobSelect) return;
    
    // Check if we have a last used job stored
    const lastJobId = getLastUsedJob();
    if (lastJobId) {
        // Check if this job still exists in the dropdown
        const jobOption = jobSelect.querySelector(`option[value="${lastJobId}"]`);
        if (jobOption) {
            // Pre-select the last used job
            jobSelect.value = lastJobId;
            console.log(`Auto-selected last used job: ${lastJobId}`);
            
            // Trigger the job change event to load activities and apply smart sorting
            jobSelect.dispatchEvent(new Event('change'));
        }
    }
}

/**
 * Get the last used job ID from localStorage
 */
function getLastUsedJob() {
    return localStorage.getItem('lastJobId');
}

/**
 * Set the last used job ID in localStorage
 */
function setLastUsedJob(jobId) {
    localStorage.setItem('lastJobId', jobId);
    console.log(`Stored last used job: ${jobId}`);
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
            
            // Find the closest hours input field - works with both old and new layouts
            let hoursInput = e.target.closest('.col-md-4, .col-md-6');
            if (hoursInput) {
                hoursInput = hoursInput.querySelector('input[type="number"]');
            }
            
            // If still not found, try searching the entire form
            if (!hoursInput) {
                hoursInput = document.querySelector('#hours_1');
            }
            
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
            const parentCol = e.target.closest('.col-md-4');
            const buttonGroup = parentCol ? parentCol.querySelector('.btn-group') : null;
            
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
