/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:        '#0D0D0F',
        surface:   '#161618',
        border:    '#2A2A2E',
        accent:    '#7B61FF',
        danger:    '#FF4D4D',
        success:   '#22C55E',
        warning:   '#F59E0B',
        'text-primary':   '#F2F2F3',
        'text-secondary': '#8A8A96',
      },
      fontFamily: {
        mono:  ['DM Mono', 'monospace'],
        serif: ['Instrument Serif', 'serif'],
      },
    },
  },
  plugins: [],
}
