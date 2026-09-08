/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        warm: {
          50: '#fdfbf7',
          100: '#f7f4ed',
          200: '#eee7d8',
          300: '#e0d4be',
          400: '#cebca0',
          500: '#b8a183',
          600: '#9f856a',
          700: '#826b54',
          800: '#695746',
          900: '#56483b',
          950: '#2e251e',
        },
        sage: {
          50: '#f4f7f4',
          100: '#e5ece5',
          200: '#ccdccd',
          300: '#a7c3a8',
          400: '#7ba27d',
          500: '#5b855e',
          600: '#466a49',
          700: '#39543c',
          800: '#304432',
          900: '#28392a',
        },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
