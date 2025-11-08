#!/usr/bin/env node

/**
 * Cross-platform migration script to run migrations in correct order
 * 1. NestJS migrations (Drizzle) - must run first
 * 2. AI Engine migrations (Alembic) - runs after NestJS
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

// Colors for output
const colors = {
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  reset: '\x1b[0m',
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function execCommand(command, cwd, description) {
  try {
    log(description, 'yellow');
    execSync(command, { 
      cwd, 
      stdio: 'inherit',
      shell: true 
    });
    return true;
  } catch (error) {
    log(`❌ Error: ${description} failed`, 'red');
    process.exit(1);
  }
}

// Get directories
const scriptDir = __dirname;
const rootDir = path.resolve(scriptDir, '..');
const apiDir = path.join(rootDir, 'services', 'api');
const aiEngineDir = path.join(rootDir, 'services', 'ai-engine');

// Check if directories exist
if (!fs.existsSync(apiDir)) {
  log(`❌ Error: API directory not found at ${apiDir}`, 'red');
  process.exit(1);
}

if (!fs.existsSync(aiEngineDir)) {
  log(`❌ Error: AI Engine directory not found at ${aiEngineDir}`, 'red');
  process.exit(1);
}

log('🚀 Starting migration process...', 'cyan');
console.log('');

// Step 1: Run NestJS migrations (Drizzle)
log('📦 Step 1: Running NestJS migrations (Drizzle)...', 'yellow');

if (!fs.existsSync(path.join(apiDir, 'package.json'))) {
  log('❌ Error: package.json not found in API directory', 'red');
  process.exit(1);
}

// Check if node_modules exists
if (!fs.existsSync(path.join(apiDir, 'node_modules'))) {
  log('⚠️  node_modules not found. Installing dependencies...', 'yellow');
  execCommand('npm install', apiDir, 'Installing dependencies');
}

// Run Drizzle migrations
log('Running Drizzle migrations...', 'yellow');
try {
  // Try npm script first, then npx
  execCommand('npx drizzle-kit push', apiDir, 'Running Drizzle migrations');
  log('✅ NestJS migrations completed successfully', 'green');
} catch (error) {
  log('❌ Error: NestJS migrations failed', 'red');
  process.exit(1);
}

console.log('');

// Step 2: Run AI Engine migrations (Alembic)
log('🤖 Step 2: Running AI Engine migrations (Alembic)...', 'yellow');

if (!fs.existsSync(path.join(aiEngineDir, 'alembic.ini'))) {
  log('❌ Error: alembic.ini not found in AI Engine directory', 'red');
  process.exit(1);
}

// Check if virtual environment exists (optional)
const venvPaths = [
  path.join(aiEngineDir, 'venv'),
  path.join(aiEngineDir, '.venv'),
];

let venvPath = null;
for (const venv of venvPaths) {
  if (fs.existsSync(venv)) {
    venvPath = venv;
    break;
  }
}

// Run Alembic migrations
log('Running Alembic migrations...', 'yellow');
try {
  const isWindows = process.platform === 'win32';
  let alembicCmd = 'alembic upgrade head';
  
  if (venvPath && !isWindows) {
    // Activate venv on Unix systems
    alembicCmd = `source ${path.join(venvPath, 'bin', 'activate')} && ${alembicCmd}`;
  } else if (venvPath && isWindows) {
    // Use venv Python on Windows
    const pythonPath = path.join(venvPath, 'Scripts', 'python.exe');
    if (fs.existsSync(pythonPath)) {
      alembicCmd = `${pythonPath} -m alembic upgrade head`;
    }
  }
  
  execCommand(alembicCmd, aiEngineDir, 'Running Alembic migrations');
  log('✅ AI Engine migrations completed successfully', 'green');
} catch (error) {
  log('❌ Error: AI Engine migrations failed', 'red');
  process.exit(1);
}

console.log('');
log('🎉 All migrations completed successfully!', 'green');

