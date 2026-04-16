/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        dark: '#0a0f1c',
        workspace: '#f8f9fc',
        surface: '#ffffff',
        border: '#e5e7eb',
        accent: {
          DEFAULT: '#2563eb',
          soft: 'rgba(37, 99, 235, 0.08)',
        },
        brand: {
          50: '#f7f6f3',
          100: '#ebe8e1',
          200: '#d5cfc3',
          300: '#b8af9e',
          400: '#9a8e7a',
          500: '#7d6f5b',
          600: '#635748',
          700: '#4a4137',
          800: '#322c26',
          900: '#1a1714',
        },
        ocean: {
          50: '#f0f7fa',
          100: '#d9edf4',
          200: '#b3dbe9',
          300: '#7cc1d9',
          400: '#4da6c7',
          500: '#2d8aad',
          600: '#226d8a',
          700: '#1c576e',
          800: '#19485b',
          900: '#153c4c',
        },
      },
      fontFamily: {
        display: ['"Noto Serif SC"', 'serif'],
        body: ['"Noto Sans SC"', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '1rem',
        'xl': '0.75rem',
      },
      keyframes: {
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'fade-in': 'fadeIn 0.5s ease-out forwards',
      },
    },
  },
  plugins: [],
}
