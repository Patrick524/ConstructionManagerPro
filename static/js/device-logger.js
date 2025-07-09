/**
 * Device logging utility for audit trail
 * Silently logs device information when workers clock in/out
 */

class DeviceLogger {
    constructor() {
        this.deviceId = this.getOrCreateDeviceId();
        this.userAgent = navigator.userAgent;
        this.currentPosition = null;
        this.isLoggingEnabled = true;
        
        // Start getting location immediately
        this.updateLocation();
        
        // Update location every 30 seconds
        setInterval(() => this.updateLocation(), 30000);
    }
    
    /**
     * Get or create a unique device ID stored in localStorage
     */
    getOrCreateDeviceId() {
        let deviceId = localStorage.getItem('deviceId');
        if (!deviceId) {
            deviceId = this.generateUUID();
            localStorage.setItem('deviceId', deviceId);
        }
        return deviceId;
    }
    
    /**
     * Generate a UUID v4
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
    
    /**
     * Update current GPS location
     */
    updateLocation() {
        if (!navigator.geolocation) {
            console.log('Geolocation not supported');
            return;
        }
        
        navigator.geolocation.getCurrentPosition(
            (position) => {
                this.currentPosition = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    accuracy: position.coords.accuracy
                };
            },
            (error) => {
                console.log('Location error:', error.message);
                this.currentPosition = null;
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 60000
            }
        );
    }
    
    /**
     * Log device action silently
     * @param {string} action - 'IN' or 'OUT'
     */
    async logAction(action) {
        if (!this.isLoggingEnabled) {
            return;
        }
        
        try {
            const logData = {
                action: action,
                deviceId: this.deviceId,
                userAgent: this.userAgent,
                lat: this.currentPosition?.lat || null,
                lng: this.currentPosition?.lng || null
            };
            
            // Send to backend - don't wait for response to avoid blocking
            fetch('/api/device-log', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(logData)
            }).catch(error => {
                // Silently handle errors - don't block the main action
                console.log('Device logging error:', error);
            });
            
        } catch (error) {
            // Silently handle any errors
            console.log('Device logging error:', error);
        }
    }
    
    /**
     * Initialize device logging for clock buttons
     */
    initializeClockLogging() {
        // Log on clock in button click
        const clockInButton = document.getElementById('clockInButton');
        if (clockInButton) {
            clockInButton.addEventListener('click', () => {
                this.logAction('IN');
            });
        }
        
        // Log on clock out button click
        const clockOutButton = document.getElementById('clockOutButton');
        if (clockOutButton) {
            clockOutButton.addEventListener('click', () => {
                this.logAction('OUT');
            });
        }
        
        // Also listen for form submissions as backup
        const clockInForm = document.getElementById('clockInForm');
        if (clockInForm) {
            clockInForm.addEventListener('submit', () => {
                this.logAction('IN');
            });
        }
        
        const clockOutForm = document.getElementById('clockOutForm');
        if (clockOutForm) {
            clockOutForm.addEventListener('submit', () => {
                this.logAction('OUT');
            });
        }
    }
}

// Initialize device logger when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (typeof window.deviceLogger === 'undefined') {
        window.deviceLogger = new DeviceLogger();
        window.deviceLogger.initializeClockLogging();
    }
});