/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: '#12181d',
          dark: '#eef0ec',
        },
        paper: {
          DEFAULT: '#f1f2ed',
          raised: '#ffffff',
          dark: '#0d1215',
          'raised-dark': '#161d21',
        },
        teal: {
          DEFAULT: '#0b6e5a',
          soft: '#0b6e5a1a',
          dark: '#33a98a',
          'soft-dark': '#33a98a26',
        },
        slate: {
          DEFAULT: '#5c6670',
          soft: '#5c667026',
          dark: '#8b95a0',
        },
        amber: {
          DEFAULT: '#a8650f',
          soft: '#c17f1e1f',
          dark: '#d99a3d',
        },
        brick: {
          DEFAULT: '#a83e32',
          soft: '#a83e321f',
          dark: '#d17a6d',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'Segoe UI', 'Helvetica Neue', 'sans-serif'],
        mono: ['Fira Code', 'ui-monospace', 'SF Mono', 'Cascadia Code', 'monospace'],
        serif: ['Source Serif 4', 'ui-serif', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: '0 1px 2px #12181d0d, 0 8px 24px -12px #12181d26',
        'card-dark': '0 1px 2px #00000040, 0 12px 28px -14px #00000080',
      },
      borderRadius: {
        sm: '5px',
        md: '8px',
        lg: '12px',
      },
    },
  },
  plugins: [],
}
