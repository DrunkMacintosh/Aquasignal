/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // "Daylight Lab" palette: a cool, near-white instrument canvas, deep
        // navy-slate ink, and an electric cobalt accent. Token NAMES are kept
        // from the previous "survey ledger" theme so the whole app re-skins
        // from here; only the values changed.
        paper: '#E9EEF5', // cool light canvas (page + recessed surfaces)
        surface: '#FBFCFE', // raised near-white card fill
        ink: {
          DEFAULT: '#0B1F33', // deep cool navy-slate
          soft: '#46586C',
          faint: '#8493A6',
        },
        // Primary accent — kept under the `water` name so existing
        // bg-water / text-water / focus styling flips automatically.
        water: {
          DEFAULT: '#1F46E5', // electric cobalt (6.4:1 on white — AA)
          deep: '#1531B0', // hover / small text on light
          wash: '#E9EDFF', // pale accent surface (badges, tints)
        },
        // Secondary / data accent — a cyan nod to the product's water identity.
        cyan: {
          DEFAULT: '#0AA2C7',
          deep: '#077E9B',
          wash: '#E0F4FA',
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
        // Common, native system fonts — familiar everywhere, no webfont load.
        display: ['system-ui', '-apple-system', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        body: ['system-ui', '-apple-system', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        // Cool, crisp shadows: a tight contact line plus a soft diffuse lift.
        card: '0 1px 2px rgba(11,31,51,0.06), 0 18px 44px -22px rgba(11,31,51,0.28)',
        sheet: '0 -10px 40px -10px rgba(11,31,51,0.30)',
        // Cobalt focus/hover glow for primary surfaces.
        glow: '0 0 0 1px rgba(31,70,229,0.35), 0 10px 30px -10px rgba(31,70,229,0.50)',
        // Inset highlight that gives frosted glass its top "lit edge".
        glass: 'inset 0 1px 0 rgba(255,255,255,0.65), 0 1px 2px rgba(11,31,51,0.05), 0 20px 50px -24px rgba(11,31,51,0.30)',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'contour-drift': {
          from: { transform: 'translateY(0)' },
          to: { transform: 'translateY(-48px)' },
        },
        'dot-bounce': {
          '0%, 80%, 100%': { transform: 'translateY(0)', opacity: '0.4' },
          '40%': { transform: 'translateY(-4px)', opacity: '1' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(24px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        // A soft cobalt pulse for "live" status indicators.
        'glow-pulse': {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 0 0 rgba(31,70,229,0.45)' },
          '50%': { opacity: '0.65', boxShadow: '0 0 0 5px rgba(31,70,229,0)' },
        },
        // A scanning sweep for loading surfaces (instrument "acquiring" feel).
        scan: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(120%)' },
        },
        // Progress/meter bars growing in from the left.
        'grow-x': {
          from: { transform: 'scaleX(0)' },
          to: { transform: 'scaleX(1)' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.6s linear infinite',
        'fade-up': 'fade-up 420ms cubic-bezier(0.16,1,0.3,1) both',
        'contour-drift': 'contour-drift 14s linear infinite',
        'dot-bounce': 'dot-bounce 1.1s ease-in-out infinite',
        'slide-in-right': 'slide-in-right 280ms cubic-bezier(0.16,1,0.3,1) both',
        'glow-pulse': 'glow-pulse 2.4s ease-in-out infinite',
        scan: 'scan 1.8s cubic-bezier(0.45,0,0.55,1) infinite',
        'grow-x': 'grow-x 800ms cubic-bezier(0.16,1,0.3,1) both',
      },
    },
  },
  plugins: [],
};
