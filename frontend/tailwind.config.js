/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // "Survey ledger" palette: warm paper surfaces, deep ink, water teal.
        paper: '#F4F1E9',
        surface: '#FDFCF7',
        ink: {
          DEFAULT: '#1C2B33',
          soft: '#51626C',
          faint: '#8B98A0',
        },
        water: {
          DEFAULT: '#0E6E83',
          deep: '#0A4F5E',
          wash: '#E3EEF0',
        },
        // Risk bands are a fixed public contract (matches backend thresholds
        // 25/50/75 in backend/core/scoring.py) — do not restyle.
        risk: {
          low: '#4CAF50',
          medium: '#FFC107',
          high: '#FF5722',
          critical: '#B71C1C',
        },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', 'Georgia', 'serif'],
        body: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(28,43,51,0.06), 0 8px 24px -12px rgba(28,43,51,0.25)',
        sheet: '0 -8px 32px -8px rgba(28,43,51,0.35)',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'contour-drift': {
          from: { transform: 'translateY(0)' },
          to: { transform: 'translateY(-48px)' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s linear infinite',
        'fade-up': 'fade-up 320ms cubic-bezier(0.16,1,0.3,1) both',
        'contour-drift': 'contour-drift 14s linear infinite',
      },
    },
  },
  plugins: [],
};
