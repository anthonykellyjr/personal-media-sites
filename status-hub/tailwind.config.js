import baseConfig from '../tailwind.config.js'

/** @type {import('tailwindcss').Config} */
export default {
  ...baseConfig,
  content: [
    './index.html',
    './src/**/*.{vue,js}',
    '../packages/shared/**/*.{vue,js}'
  ]
}
