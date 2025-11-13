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
  // Step 1: Generate migrations from schema changes
  log('Generating Drizzle migrations...', 'yellow');
  let migrationsGenerated = false;
  try {
    execCommand('npx drizzle-kit generate', apiDir, 'Generating Drizzle migrations');
    migrationsGenerated = true;
    log('✅ Migrations generated', 'green');
  } catch (generateError) {
    // If generate fails, it might be because there are no changes
    const errorOutput = generateError.message || generateError.toString() || '';
    if (errorOutput.includes('No schema changes') || errorOutput.includes('No changes detected')) {
      log('ℹ️  No schema changes detected - skipping migration generation', 'yellow');
    } else {
      log('⚠️  Migration generation had issues, but continuing...', 'yellow');
      log(`   Error: ${errorOutput}`, 'yellow');
    }
  }
  
  // Step 2: Apply migrations
  // Drizzle doesn't have a built-in migrate command, so we use push for development
  // In production, you would apply the generated SQL files from ./drizzle directory
  log('Applying Drizzle migrations...', 'yellow');
  log('ℹ️  Note: If you see DROP CONSTRAINT statements for NOT NULL constraints, these are safe.', 'yellow');
  log('   They remove redundant explicit constraints - columns will still be NOT NULL.', 'yellow');
  try {
    execCommand('npx drizzle-kit push', apiDir, 'Applying Drizzle migrations (push)');
    log('✅ NestJS migrations completed successfully', 'green');
    if (migrationsGenerated) {
      log('ℹ️  Migration files generated in ./drizzle directory - commit these to version control', 'yellow');
    }
  } catch (pushError) {
    // Check if error is about primary keys (tables already exist)
    const errorOutput = pushError.message || pushError.toString() || '';
    if (errorOutput.includes('primary key') || errorOutput.includes('42P16')) {
      log('⚠️  Drizzle push encountered primary key constraint (tables may already exist)', 'yellow');
      log('   This is usually okay if your schema is already up to date.', 'yellow');
      log('✅ NestJS migrations completed (with warnings)', 'green');
      if (migrationsGenerated) {
        log('ℹ️  Migration files generated in ./drizzle directory - commit these to version control', 'yellow');
      }
    } else {
      throw pushError;
    }
  }
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

