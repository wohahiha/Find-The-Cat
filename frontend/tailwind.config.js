/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: '#2547f4',
        'primary-foreground': '#ffffff',
        'primary-green': '#13ec5b',
        'background-light': '#f5f6f8',
        'background-dark': '#101322',
        panel: '#14182c',
        input: '#181d34',
        'input-border': '#313a68',
        'border-panel': '#222949',
        muted: '#909acb',
        text: '#e8ecff',
        danger: '#ec1313',
      },
      fontFamily: {
        display: ['Manrope', 'sans-serif'],
        alt: ['Space Grotesk', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '0.25rem',
        lg: '0.5rem',
        xl: '0.75rem',
        full: '9999px',
      },
      boxShadow: {
        panel: '0 20px 50px rgba(0,0,0,0.35)',
      },
    },
  },
  plugins: [],
}
