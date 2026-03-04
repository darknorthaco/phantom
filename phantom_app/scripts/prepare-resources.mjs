/**
 * prepare-resources.mjs
 *
 * Copies the minimal phantom_core files needed to run the controller
 * into src-tauri/resources/phantom_core/ so Tauri can bundle them.
 *
 * Run automatically via tauri.conf.json beforeBuildCommand.
 * Safe to run multiple times (incremental copy).
 */

import { copyFileSync, mkdirSync, readdirSync, statSync, rmSync, existsSync } from 'fs';
import { join, dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Resolve paths relative to this script's location (phantom_app/scripts/)
const PHANTOM_CORE_SRC = resolve(__dirname, '../../phantom_core');
const DEST_ROOT = resolve(__dirname, '../src-tauri/resources/phantom_core');

// Python packages / directories to include
const INCLUDE_DIRS = [
  'phantom_core',
  'security_framework',
  'socket_infrastructure',
  'llm_taskmaster',
  'phantom_protocol',
  'phantom_protocol_schemas',
  'linux-worker',
];

// Top-level files to include
const INCLUDE_FILES = [
  'run.py',
  'run_integrated_phantom.py',
  'requirements.txt',
  'setup.py',
];

// Directory / file names to skip when recursing
const SKIP_NAMES = new Set([
  '__pycache__',
  '.git',
  '.github',
  'venv',
  '.venv',
  'node_modules',
  '.pytest_cache',
  '.mypy_cache',
  '*.egg-info',
  'dist',
  'build',
]);

function shouldSkip(name) {
  return SKIP_NAMES.has(name) || name.endsWith('.egg-info') || name.endsWith('.pyc');
}

function copyDirRecursive(src, dest) {
  if (!existsSync(src)) return;
  mkdirSync(dest, { recursive: true });

  for (const entry of readdirSync(src)) {
    if (shouldSkip(entry)) continue;

    const srcPath  = join(src, entry);
    const destPath = join(dest, entry);
    const stat     = statSync(srcPath);

    if (stat.isDirectory()) {
      copyDirRecursive(srcPath, destPath);
    } else {
      copyFileSync(srcPath, destPath);
    }
  }
}

// ── Main ────────────────────────────────────────────────────────────

console.log(`\n[prepare-resources] Bundling phantom_core into Tauri resources`);
console.log(`  src : ${PHANTOM_CORE_SRC}`);
console.log(`  dest: ${DEST_ROOT}\n`);

if (!existsSync(PHANTOM_CORE_SRC)) {
  console.warn(`[prepare-resources] WARNING: phantom_core not found at ${PHANTOM_CORE_SRC}`);
  console.warn('  Skipping resource prep — build will use dev path fallback.\n');
  process.exit(0);
}

// Clean the destination so we don't accumulate stale files
if (existsSync(DEST_ROOT)) {
  rmSync(DEST_ROOT, { recursive: true, force: true });
}
mkdirSync(DEST_ROOT, { recursive: true });

// Copy selected directories
for (const dir of INCLUDE_DIRS) {
  const src  = join(PHANTOM_CORE_SRC, dir);
  const dest = join(DEST_ROOT, dir);
  if (existsSync(src)) {
    copyDirRecursive(src, dest);
    console.log(`  [dir ] ${dir}/`);
  } else {
    console.log(`  [skip] ${dir}/ (not found)`);
  }
}

// Copy top-level files
for (const file of INCLUDE_FILES) {
  const src  = join(PHANTOM_CORE_SRC, file);
  const dest = join(DEST_ROOT, file);
  if (existsSync(src)) {
    copyFileSync(src, dest);
    console.log(`  [file] ${file}`);
  } else {
    console.log(`  [skip] ${file} (not found)`);
  }
}

console.log('\n[prepare-resources] Done.\n');
