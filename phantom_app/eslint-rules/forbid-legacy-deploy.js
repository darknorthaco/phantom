const FORBIDDEN_FROM_CANONICAL = new Set([
  'runDeploymentPreScan',
  'completeDeploymentWithSelection',
  'deployPhantom',
  'upgradePhantomDeployment',
  'scanAndRegisterWorkers',
  'runDeploymentPreScanLegacy',
  'completeDeploymentWithSelectionLegacy',
  'deployPhantomLegacy',
  'upgradePhantomDeploymentLegacy',
]);

/**
 * PR-I — forbid legacy deploy usage in canonical UI.
 *
 * This rule enforces I-NoLegacyImports:
 * - No imports from `utils/tauri.legacy.ts` anywhere in canonical source.
 * - No legacy symbol names imported from `utils/tauri.ts`.
 */
export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Forbid legacy deploy imports in canonical UI',
    },
    schema: [],
    messages: {
      legacyModule:
        'Legacy deploy module import is forbidden in ceremony-first code.',
      legacySymbol:
        'Legacy deploy symbol "{{name}}" is forbidden in canonical ceremony-first code.',
    },
  },
  create(context) {
    return {
      ImportDeclaration(node) {
        const source = node.source?.value;
        if (typeof source !== 'string') return;

        if (source.includes('/utils/tauri.legacy')) {
          context.report({ node, messageId: 'legacyModule' });
          return;
        }

        if (!source.includes('/utils/tauri')) return;
        for (const spec of node.specifiers ?? []) {
          if (spec.type !== 'ImportSpecifier') continue;
          const importedName = spec.imported?.name;
          if (!importedName) continue;
          if (FORBIDDEN_FROM_CANONICAL.has(importedName)) {
            context.report({
              node: spec,
              messageId: 'legacySymbol',
              data: { name: importedName },
            });
          }
        }
      },
    };
  },
};
