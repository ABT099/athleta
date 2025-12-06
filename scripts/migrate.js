#!/usr/bin/env node

/**
 * Orchestrator: Shared Database Migration
 * 1. API (NestJS/Drizzle) -> Public Schema
 * 2. AI (Python/Alembic) -> AI Schema
 */

const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

// --- Configuration ---
const CONFIG = {
  apiDir: path.join(__dirname, "../services/api"),
  aiDir: path.join(__dirname, "../services/ai-engine"),
  verbose: true,
};

// --- Helpers ---
const colors = {
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  cyan: "\x1b[36m",
  reset: "\x1b[0m",
  dim: "\x1b[2m",
};

function log(msg, color = "reset") {
  console.log(`${colors[color]}${msg}${colors.reset}`);
}

function run(command, cwd, stepName) {
  try {
    if (CONFIG.verbose) log(`   $ ${command}`, "dim");
    execSync(command, { cwd, stdio: "inherit", shell: true });
    return true;
  } catch (error) {
    log(`\n❌ FAILED: ${stepName}`, "red");
    process.exit(1); // Fail fast
  }
}

// --- Main Execution ---
(function main() {
  console.clear();
  log("🔗 Shared Database Migration Orchestrator", "cyan");
  log("========================================\n");

  // 0. Pre-flight Checks
  if (!fs.existsSync(CONFIG.apiDir) || !fs.existsSync(CONFIG.aiDir)) {
    log("❌ Error: Service directories not found. Check paths.", "red");
    process.exit(1);
  }

  // ---------------------------------------------------------
  // STEP 1: NESTJS (Drizzle)
  // ---------------------------------------------------------
  log("📦 Step 1: API Schema (Drizzle)", "yellow");

  // Ensure deps
  if (!fs.existsSync(path.join(CONFIG.apiDir, "node_modules"))) {
    log("   Installing API dependencies...", "dim");
    run("npm ci", CONFIG.apiDir, "API Install");
  }

  // A. Generate SQL files based on schema.ts
  log("   Generating migration files...", "cyan");
  run("npx drizzle-kit generate", CONFIG.apiDir, "Drizzle Generate");

  // B. Apply those files to the DB
  // Note: We use 'migrate', not 'push', to ensure history is respected
  log("   Applying migrations to DB...", "cyan");
  run("npx drizzle-kit migrate", CONFIG.apiDir, "Drizzle Migrate");

  log("✅ API Migrations Synced\n", "green");

  // ---------------------------------------------------------
  // STEP 2: AI ENGINE (Alembic)
  // ---------------------------------------------------------
  log("🧠 Step 2: AI Schema (Alembic)", "yellow");

  // Detect Python Environment
  const venvPath = path.join(CONFIG.aiDir, "venv");
  const isWin = process.platform === "win32";
  let pythonExec = "python"; // Default fallback

  if (fs.existsSync(venvPath)) {
    pythonExec = isWin
      ? path.join(venvPath, "Scripts", "python.exe")
      : path.join(venvPath, "bin", "python");
  } else {
    log("⚠️  No venv found, attempting to use system python...", "yellow");
  }

  // Install deps if needed (optional, can comment out if slow)
  // run(`${pythonExec} -m pip install -r requirements.txt`, CONFIG.aiDir, 'Pip Install');

  // Run Alembic
  // We use python -m alembic to ensure we use the venv's alembic, not global
  log("   Running Alembic upgrade...", "cyan");
  run(`${pythonExec} -m alembic upgrade head`, CONFIG.aiDir, "Alembic Upgrade");

  log("✅ AI Migrations Synced\n", "green");

  // ---------------------------------------------------------
  // FINISH
  // ---------------------------------------------------------
  log("🎉 All Systems Operational. Database is consistent.", "green");
})();
