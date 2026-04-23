/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  corePlugins: {
    preflight: false, // don't override existing CSS resets
  },
  theme: {
    extend: {},
  },
  plugins: [],
}

