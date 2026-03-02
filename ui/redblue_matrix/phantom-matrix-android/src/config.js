/**
 * Phantom Matrix Android App Configuration
 * Update BACKEND_URL to match your Phantom server address.
 */

export const CONFIG = {
    // Set during installation — installer writes discovered controller address
    BACKEND_URL: 'ws://localhost:8081',
    RECONNECT_TIMEOUT: 3000,
    MAX_RETRIES: 5,

    // Performance settings
    MATRIX_DROPS_MOBILE: 30,
    ANIMATION_FPS: 60,

    // Features
    VOICE_INPUT_ENABLED: true,
    NOTIFICATIONS_ENABLED: true,

    // Branding
    COMPANY_NAME: 'Dark North Co.',
};
