// Flat config for ESLint 9. The plugins below were already dependencies —
// `npm run lint` had no config file to use them with, so it never ran.
import js from '@eslint/js';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default [
  { ignores: ['dist', 'e2e/**', 'playwright-report/**', 'test-results/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: globals.browser,
    },
    plugins: { '@typescript-eslint': tsPlugin, 'react-hooks': reactHooks },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'no-unused-vars': 'off',
      // TypeScript already checks every identifier at compile time, globals
      // included, and does it against ambient *type* declarations (DOM lib
      // interfaces like RequestInit) that no-undef's JS-level scope analysis
      // cannot see. The typescript-eslint docs recommend this rule off.
      'no-undef': 'off',
      // CLAUDE.md: "No `any` in web/src/". tsc strict does not flag `any`
      // on its own; this is the rule that actually enforces the sentence.
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
];
