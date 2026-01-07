/**
 * Passkey (WebAuthn) JavaScript for BuilderTime Pro
 *
 * Handles passkey registration and authentication using the Web Authentication API.
 * Limited to platform authenticators (Face ID / Touch ID on iPhone).
 */

// Utility functions for base64url encoding/decoding
function base64urlToBuffer(base64url) {
    const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
    const padding = '='.repeat((4 - base64.length % 4) % 4);
    const binary = atob(base64 + padding);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

function bufferToBase64url(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    const base64 = btoa(binary);
    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

// Check if WebAuthn is supported
function isWebAuthnSupported() {
    return window.PublicKeyCredential !== undefined &&
           typeof window.PublicKeyCredential === 'function';
}

// Check if platform authenticator is available (Face ID / Touch ID)
async function isPlatformAuthenticatorAvailable() {
    if (!isWebAuthnSupported()) {
        return false;
    }
    try {
        return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch (e) {
        console.error('Error checking platform authenticator:', e);
        return false;
    }
}

/**
 * Register a new passkey for the current user
 * @param {string} passkeyName - Optional name for the passkey
 * @returns {Promise<object>} - Result object with success/error
 */
async function registerPasskey(passkeyName = 'My iPhone') {
    // Check WebAuthn support
    if (!isWebAuthnSupported()) {
        return { success: false, error: 'WebAuthn is not supported on this device.' };
    }

    // Check for platform authenticator
    const hasPlatformAuth = await isPlatformAuthenticatorAvailable();
    if (!hasPlatformAuth) {
        return { success: false, error: 'Face ID or Touch ID is not available on this device.' };
    }

    try {
        // Step 1: Get registration options from server
        const beginResponse = await fetch('/passkey/register/begin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (!beginResponse.ok) {
            const errorData = await beginResponse.json();
            return { success: false, error: errorData.error || 'Failed to start registration.' };
        }

        const options = await beginResponse.json();

        // Step 2: Convert base64url strings to ArrayBuffers
        options.challenge = base64urlToBuffer(options.challenge);
        options.user.id = base64urlToBuffer(options.user.id);

        if (options.excludeCredentials) {
            options.excludeCredentials = options.excludeCredentials.map(cred => ({
                ...cred,
                id: base64urlToBuffer(cred.id),
            }));
        }

        // Step 3: Call WebAuthn API to create credential
        const credential = await navigator.credentials.create({
            publicKey: options
        });

        // Step 4: Prepare credential for server
        const credentialData = {
            id: credential.id,
            rawId: bufferToBase64url(credential.rawId),
            type: credential.type,
            response: {
                clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
                attestationObject: bufferToBase64url(credential.response.attestationObject),
                transports: credential.response.getTransports ? credential.response.getTransports() : [],
            },
            passkey_name: passkeyName,
        };

        // Step 5: Send credential to server for verification
        const finishResponse = await fetch('/passkey/register/finish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentialData),
        });

        const result = await finishResponse.json();

        if (!finishResponse.ok) {
            return { success: false, error: result.error || 'Registration failed.' };
        }

        return { success: true, message: result.message };

    } catch (error) {
        console.error('Passkey registration error:', error);

        // Handle specific WebAuthn errors
        if (error.name === 'NotAllowedError') {
            return { success: false, error: 'Registration was cancelled or not allowed.' };
        } else if (error.name === 'InvalidStateError') {
            return { success: false, error: 'This passkey is already registered.' };
        } else if (error.name === 'NotSupportedError') {
            return { success: false, error: 'This device does not support passkeys.' };
        }

        return { success: false, error: error.message || 'An unexpected error occurred.' };
    }
}

/**
 * Authenticate with a passkey
 * @param {string} email - User's email address
 * @returns {Promise<object>} - Result object with success/error and redirect URL
 */
async function authenticateWithPasskey(email) {
    // Check WebAuthn support
    if (!isWebAuthnSupported()) {
        return { success: false, error: 'WebAuthn is not supported on this device.' };
    }

    if (!email || email.trim() === '') {
        return { success: false, error: 'Please enter your email address.' };
    }

    try {
        // Step 1: Get authentication options from server
        const beginResponse = await fetch('/passkey/auth/begin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email.trim() }),
        });

        if (!beginResponse.ok) {
            const errorData = await beginResponse.json();
            return { success: false, error: errorData.error || 'Failed to start authentication.' };
        }

        const options = await beginResponse.json();

        // Step 2: Convert base64url strings to ArrayBuffers
        options.challenge = base64urlToBuffer(options.challenge);

        if (options.allowCredentials) {
            options.allowCredentials = options.allowCredentials.map(cred => ({
                ...cred,
                id: base64urlToBuffer(cred.id),
            }));
        }

        // Step 3: Call WebAuthn API to get credential assertion
        const credential = await navigator.credentials.get({
            publicKey: options
        });

        // Step 4: Prepare assertion for server
        const assertionData = {
            id: credential.id,
            rawId: bufferToBase64url(credential.rawId),
            type: credential.type,
            response: {
                clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
                authenticatorData: bufferToBase64url(credential.response.authenticatorData),
                signature: bufferToBase64url(credential.response.signature),
                userHandle: credential.response.userHandle ?
                    bufferToBase64url(credential.response.userHandle) : null,
            },
        };

        // Step 5: Send assertion to server for verification
        const finishResponse = await fetch('/passkey/auth/finish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(assertionData),
        });

        const result = await finishResponse.json();

        if (!finishResponse.ok) {
            return { success: false, error: result.error || 'Authentication failed.' };
        }

        return {
            success: true,
            message: result.message,
            redirect: result.redirect,
        };

    } catch (error) {
        console.error('Passkey authentication error:', error);

        // Handle specific WebAuthn errors
        if (error.name === 'NotAllowedError') {
            return { success: false, error: 'Authentication was cancelled or not allowed.' };
        } else if (error.name === 'InvalidStateError') {
            return { success: false, error: 'No matching passkey found.' };
        }

        return { success: false, error: error.message || 'An unexpected error occurred.' };
    }
}

// Export functions for use in templates
window.PasskeyAuth = {
    isSupported: isWebAuthnSupported,
    isPlatformAvailable: isPlatformAuthenticatorAvailable,
    register: registerPasskey,
    authenticate: authenticateWithPasskey,
};
