#!/usr/bin/env node

/**
 * stale-check.mjs — Detect potentially stale memories referencing changed files.
 *
 * Runs as a Stop hook. Checks if any memory content references files
 * that have been modified in the working tree. Outputs warnings to stderr.
 * Always exits 0 (never blocks session).
 */

import { DatabaseSync } from "node:sqlite";
import { execSync } from "node:child_process";
import { resolve, basename, dirname } from "node:path";

const DB_PATH = resolve(
  process.env.MEMORY_DB_PATH ||
    resolve(import.meta.dirname, "memory.db")
);

try {
  // Get changed files from git
  const diffOutput = execSync("git diff --name-only HEAD 2>/dev/null", {
    encoding: "utf-8",
  }).trim();
  const untrackedOutput = execSync(
    "git ls-files --others --exclude-standard 2>/dev/null",
    { encoding: "utf-8" }
  ).trim();

  const changedFiles = [
    ...diffOutput.split("\n"),
    ...untrackedOutput.split("\n"),
  ].filter(Boolean);

  if (changedFiles.length === 0) {
    process.exit(0);
  }

  // Build search patterns from changed files
  const patterns = new Set();
  for (const file of changedFiles) {
    patterns.add(file); // full path
    patterns.add(basename(file)); // base name
    const dir = dirname(file);
    if (dir !== ".") {
      patterns.add(dir); // parent directory
    }
  }

  // Open DB and scan memories
  const db = new DatabaseSync(DB_PATH);
  const rows = db
    .prepare("SELECT id, type, name, content FROM memories")
    .all();

  const staleMemories = [];
  for (const row of rows) {
    const haystack = `${row.name}\n${row.content}`;
    for (const pattern of patterns) {
      if (pattern.length >= 3 && haystack.includes(pattern)) {
        staleMemories.push({ id: row.id, name: row.name, match: pattern });
        break;
      }
    }
  }

  db.close();

  if (staleMemories.length > 0) {
    process.stderr.write(
      "\n⚠️  Potentially stale memories detected (referenced files have changed):\n"
    );
    for (const m of staleMemories) {
      process.stderr.write(`   #${m.id} "${m.name}" — matches: ${m.match}\n`);
    }
    process.stderr.write(
      "   Consider reviewing these with `recall` or `forget`.\n\n"
    );
  }
} catch {
  // Silently ignore errors — never block session exit
}

process.exit(0);
