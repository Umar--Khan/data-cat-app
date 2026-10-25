/** @type {import('prettier').Config & import('prettier-plugin-tailwindcss').PluginOptions} */
export default {
  semi: false,
  singleQuote: true,
  printWidth: 100,
  overrides: [
    {
      // Scoped so formatting files outside the app never loads the frontend stylesheet.
      files: 'frontend/**',
      options: {
        plugins: ['prettier-plugin-tailwindcss'],
        tailwindStylesheet: './frontend/src/index.css',
        tailwindFunctions: ['tv', 'cn'],
      },
    },
  ],
}
