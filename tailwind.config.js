/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js}',
    './node_modules/@webhead/shared/**/*.{vue,js}'
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0a0a0f',
          800: '#12121a',
          700: '#1a1a24'
        }
      }
    }
  },
  plugins: []
}
