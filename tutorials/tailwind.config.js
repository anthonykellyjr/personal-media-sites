import baseConfig from '../tailwind.config.js'

export default {
  ...baseConfig,
  content: [
    './index.html',
    './src/**/*.{vue,js}',
    '../packages/shared/**/*.{vue,js}'
  ]
}
