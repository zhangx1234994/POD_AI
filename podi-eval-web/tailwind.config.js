/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  corePlugins: {
    // Prevent Tailwind preflight from overriding TDesign base styles.
    preflight: false,
  },
  theme: {
    extend: {},
  },
  plugins: [],
};
