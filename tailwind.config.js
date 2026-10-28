/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['"Space Grotesk"', '"JetBrains Mono"', '"Fira Code"', '"SF Mono"', 'monospace'],
                mono: ['"JetBrains Mono"', '"Fira Code"', '"SF Mono"', 'monospace'],
            },
            colors: {
                'soda-bg': '#04080B',
                'soda-void': '#0A0F14',
                'soda-accent': '#00fbfb',
                'soda-accent-dim': 'rgba(0, 251, 251, 0.4)',
                'soda-text': '#e0f0ff',
                'soda-text-dim': '#8ba0b8',
                'soda-error': '#ff4466',
                'soda-success': '#00ff88',
                'soda-warning': '#ffaa00',
                'soda-glass': 'rgba(10, 15, 20, 0.85)',
                'soda-outline': 'rgba(0, 251, 251, 0.12)',
            }
        },
    },
    plugins: [],
}
