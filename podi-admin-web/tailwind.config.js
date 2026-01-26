/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  // TDesign already ships a reset. Tailwind preflight conflicts with TDesign layout/components.
  corePlugins: { preflight: false },
  theme: {
    extend: {},
  },
  plugins: [],
}
