import tsParser from '@typescript-eslint/parser';
import forbidLegacyDeploy from './eslint-rules/forbid-legacy-deploy.js';

export default [
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      'phantom-dka': {
        rules: {
          'forbid-legacy-deploy': forbidLegacyDeploy,
        },
      },
    },
    rules: {
      'phantom-dka/forbid-legacy-deploy': 'error',
    },
  },
];
