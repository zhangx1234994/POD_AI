/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ui: {
          bg: 'rgb(var(--podi-bg) / <alpha-value>)',
          surface: 'rgb(var(--podi-surface) / <alpha-value>)',
          surface2: 'rgb(var(--podi-surface-2) / <alpha-value>)',
          text1: 'rgb(var(--podi-text-1) / <alpha-value>)',
          text2: 'rgb(var(--podi-text-2) / <alpha-value>)',
          text3: 'rgb(var(--podi-text-3) / <alpha-value>)',
          border: 'rgb(var(--podi-border) / <alpha-value>)',
          primary: 'rgb(var(--podi-primary) / <alpha-value>)',
          primaryHover: 'rgb(var(--podi-primary-hover) / <alpha-value>)',
          success: 'rgb(var(--podi-success) / <alpha-value>)',
          warning: 'rgb(var(--podi-warning) / <alpha-value>)',
          error: 'rgb(var(--podi-error) / <alpha-value>)',
        },
      },
      borderRadius: {
        ui: 'var(--podi-radius)',
      },
      boxShadow: {
        ui: '0 20px 60px rgba(var(--podi-shadow), 0.08)',
        uiLg: '0 40px 120px rgba(var(--podi-shadow), 0.10)',
      },
    },
  },
  plugins: [],
}
