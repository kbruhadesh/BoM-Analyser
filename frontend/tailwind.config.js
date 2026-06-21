/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Core surface stack (PCB-inspired dark)
        canvas:   '#0D1117',   // page background — near-black
        surface:  '#161B22',   // card / panel
        elevated: '#1C2128',   // raised element
        border:   '#30363D',   // dividers
        muted:    '#6E7681',   // tertiary text

        // Scope trace accents
        trace:    '#58A6FF',   // primary blue accent
        stock:    '#3FB950',   // in-stock / best price
        warn:     '#D29922',   // caution / mid price
        danger:   '#F85149',   // OOS / worst price
        purple:   '#BC8CFF',   // LCSC vendor tag
        orange:   '#FFA657',   // Arrow vendor tag

        // Text scale
        ink:      '#F0F6FC',   // primary text
        'ink-2':  '#C9D1D9',   // secondary text
        'ink-3':  '#8B949E',   // tertiary text
      },
      fontFamily: {
        mono:  ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans:  ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['10px', '14px'],
        'xs':  ['11px', '16px'],
        'sm':  ['12px', '18px'],
        'base':['13px', '20px'],
        'md':  ['14px', '22px'],
        'lg':  ['16px', '24px'],
        'xl':  ['18px', '28px'],
        '2xl': ['22px', '30px'],
        '3xl': ['28px', '36px'],
      },
      borderRadius: {
        DEFAULT: '4px',
        'sm': '2px',
        'md': '6px',
        'lg': '8px',
        'xl': '12px',
      },
      boxShadow: {
        'glow-blue':  '0 0 12px rgba(88,166,255,0.25)',
        'glow-green': '0 0 12px rgba(63,185,80,0.25)',
        'glow-red':   '0 0 12px rgba(248,81,73,0.25)',
        'panel':      '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(48,54,61,0.8)',
      },
      animation: {
        'pulse-slow':  'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'fade-in':     'fadeIn 0.2s ease-out',
        'slide-up':    'slideUp 0.2s ease-out',
        'scan':        'scan 2s linear infinite',
      },
      keyframes: {
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(6px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        scan: {
          '0%':   { transform: 'translateY(0)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [],
}
