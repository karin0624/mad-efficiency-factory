import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { DatabaseSync } from "node:sqlite";
import { z } from "zod";
import { resolve } from "path";

const DB_PATH = resolve(
  process.env.MEMORY_DB_PATH ||
    resolve(import.meta.dirname, "memory.db")
);

const db = new DatabaseSync(DB_PATH);
db.exec("PRAGMA journal_mode = WAL");
db.exec("PRAGMA foreign_keys = ON");

// --- Schema ---
db.exec(`
  CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('user','feedback','project','reference')),
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

// --- FTS migration: unicode61 → trigram ---
const ftsInfo = db
  .prepare(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='memories_fts'"
  )
  .get();
const needsMigration = ftsInfo && !ftsInfo.sql.includes("trigram");

if (needsMigration) {
  db.exec("DROP TRIGGER IF EXISTS memories_ai");
  db.exec("DROP TRIGGER IF EXISTS memories_ad");
  db.exec("DROP TRIGGER IF EXISTS memories_au");
  db.exec("DROP TABLE memories_fts");
}

db.exec(`
  CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    name, content, content=memories, content_rowid=id,
    tokenize='trigram'
  );
`);

if (needsMigration) {
  db.exec("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')");
}

// --- Triggers (keep FTS in sync) ---
const triggerExists = db
  .prepare(
    "SELECT name FROM sqlite_master WHERE type='trigger' AND name='memories_ai'"
  )
  .get();

if (!triggerExists) {
  db.exec(`
    CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
      INSERT INTO memories_fts(rowid, name, content) VALUES (new.id, new.name, new.content);
    END;
    CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts, rowid, name, content) VALUES('delete', old.id, old.name, old.content);
    END;
    CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts, rowid, name, content) VALUES('delete', old.id, old.name, old.content);
      INSERT INTO memories_fts(rowid, name, content) VALUES (new.id, new.name, new.content);
    END;
  `);
}

// --- Query helpers ---

/**
 * Sanitize a natural-language query for FTS5 trigram MATCH.
 * Each term is double-quoted (literal substring match) and joined with AND.
 * Terms shorter than 3 chars are dropped (trigram minimum).
 * Returns null if no usable terms remain.
 */
function sanitizeFtsQuery(query) {
  const terms = query
    .split(/\s+/)
    .filter((t) => t.length >= 3)
    .map((t) => '"' + t.replace(/"/g, '""') + '"');
  return terms.length > 0 ? terms.join(" AND ") : null;
}

// --- Prepared statements ---
const stmts = {
  insert: db.prepare(
    "INSERT INTO memories (type, name, content) VALUES (?, ?, ?)"
  ),
  update: db.prepare(
    "UPDATE memories SET name = ?, content = ?, updated_at = datetime('now') WHERE id = ?"
  ),
  delete: db.prepare("DELETE FROM memories WHERE id = ?"),
  search: db.prepare(`
    SELECT m.id, m.type, m.name, m.content, m.created_at, m.updated_at
    FROM memories_fts f
    JOIN memories m ON m.id = f.rowid
    WHERE memories_fts MATCH ?
    ORDER BY rank
    LIMIT ?
  `),
  searchByType: db.prepare(`
    SELECT m.id, m.type, m.name, m.content, m.created_at, m.updated_at
    FROM memories_fts f
    JOIN memories m ON m.id = f.rowid
    WHERE memories_fts MATCH ? AND m.type = ?
    ORDER BY rank
    LIMIT ?
  `),
  likeFallback: db.prepare(`
    SELECT id, type, name, content, created_at, updated_at
    FROM memories
    WHERE name LIKE '%' || ? || '%' OR content LIKE '%' || ? || '%'
    ORDER BY updated_at DESC
    LIMIT ?
  `),
  likeFallbackByType: db.prepare(`
    SELECT id, type, name, content, created_at, updated_at
    FROM memories
    WHERE (name LIKE '%' || ? || '%' OR content LIKE '%' || ? || '%') AND type = ?
    ORDER BY updated_at DESC
    LIMIT ?
  `),
  listByType: db.prepare(
    "SELECT id, type, name, substr(content, 1, 120) AS preview, created_at, updated_at FROM memories WHERE type = ? ORDER BY updated_at DESC LIMIT ?"
  ),
  listAll: db.prepare(
    "SELECT id, type, name, substr(content, 1, 120) AS preview, created_at, updated_at FROM memories ORDER BY updated_at DESC LIMIT ?"
  ),
  getById: db.prepare("SELECT * FROM memories WHERE id = ?"),
};

/**
 * Search with FTS5 trigram first, fall back to LIKE on error or zero results.
 */
function searchMemories(query, type, limit) {
  const ftsQuery = sanitizeFtsQuery(query);

  if (ftsQuery) {
    try {
      const rows = type
        ? stmts.searchByType.all(ftsQuery, type, limit)
        : stmts.search.all(ftsQuery, limit);
      if (rows.length > 0) return rows;
    } catch {
      // FTS5 parse error — fall through to LIKE
    }
  }

  return type
    ? stmts.likeFallbackByType.all(query, query, type, limit)
    : stmts.likeFallback.all(query, query, limit);
}

// --- MCP Server ---
const server = new McpServer({
  name: "memory",
  version: "1.0.0",
});

server.tool(
  "remember",
  `Save a memory. RULES:
- NEVER save information derivable from code, file structure, or git history
- ONLY save: WHY decisions were made, user preferences, non-obvious gotchas, external references
- Ask yourself: "Will this become wrong when the code changes?" If yes, do NOT save it.

GOOD: decision rationale, user feedback, non-documented gotchas, external URLs
BAD: architecture snapshots, API listings, implementation logs, config summaries`,
  {
    type: z
      .enum(["user", "feedback", "project", "reference"])
      .describe(
        "user=about the user, feedback=user corrections, project=project context, reference=external pointers"
      ),
    name: z.string().describe("Short descriptive name for this memory"),
    content: z.string().describe("The memory content to store"),
    justification: z
      .string()
      .describe(
        "REQUIRED: Why this memory cannot be derived from code/git. Min 10 chars."
      ),
  },
  async ({ type, name, content, justification }) => {
    if (!justification || justification.trim().length < 10) {
      return {
        content: [
          {
            type: "text",
            text: "Rejected: justification required (min 10 chars). Explain why this cannot be derived from code/git.",
          },
        ],
      };
    }
    const result = stmts.insert.run(type, name, content);
    // justificationはDBに保存しない（書き込み時の摩擦として機能するだけ）
    return {
      content: [
        {
          type: "text",
          text: `Saved memory #${result.lastInsertRowid}: [${type}] ${name}`,
        },
      ],
    };
  }
);

server.tool(
  "recall",
  "Search memories by keyword. Supports Japanese and special characters. Uses substring matching with automatic fallback.",
  {
    query: z
      .string()
      .describe("Search keywords (natural language, no special syntax needed)"),
    type: z
      .enum(["user", "feedback", "project", "reference"])
      .optional()
      .describe("Filter by memory type"),
    limit: z.number().default(10).describe("Max results to return"),
  },
  async ({ query, type, limit }) => {
    const rows = searchMemories(query, type, limit);
    if (rows.length === 0) {
      return { content: [{ type: "text", text: "No memories found." }] };
    }
    const text = rows
      .map(
        (r) =>
          `#${r.id} [${r.type}] ${r.name} (updated: ${r.updated_at})\n${r.content}`
      )
      .join("\n---\n");
    return { content: [{ type: "text", text }] };
  }
);

server.tool(
  "get_memory",
  "Get a single memory by ID with full content.",
  {
    id: z.number().describe("Memory ID"),
  },
  async ({ id }) => {
    const row = stmts.getById.get(id);
    if (!row) {
      return { content: [{ type: "text", text: `Memory #${id} not found.` }] };
    }
    const text = `#${row.id} [${row.type}] ${row.name} (created: ${row.created_at}, updated: ${row.updated_at})\n${row.content}`;
    return { content: [{ type: "text", text }] };
  }
);

server.tool(
  "forget",
  "Delete a memory by ID.",
  {
    id: z.number().describe("Memory ID to delete"),
  },
  async ({ id }) => {
    const row = stmts.getById.get(id);
    if (!row) {
      return { content: [{ type: "text", text: `Memory #${id} not found.` }] };
    }
    stmts.delete.run(id);
    return {
      content: [
        {
          type: "text",
          text: `Deleted memory #${id}: [${row.type}] ${row.name}`,
        },
      ],
    };
  }
);

server.tool(
  "update_memory",
  "Update an existing memory by ID.",
  {
    id: z.number().describe("Memory ID to update"),
    name: z.string().optional().describe("New name (omit to keep current)"),
    content: z
      .string()
      .optional()
      .describe("New content (omit to keep current)"),
  },
  async ({ id, name, content }) => {
    const row = stmts.getById.get(id);
    if (!row) {
      return { content: [{ type: "text", text: `Memory #${id} not found.` }] };
    }
    stmts.update.run(name ?? row.name, content ?? row.content, id);
    return {
      content: [
        {
          type: "text",
          text: `Updated memory #${id}: [${row.type}] ${name ?? row.name}`,
        },
      ],
    };
  }
);

server.tool(
  "list_memories",
  "List all stored memories, optionally filtered by type.",
  {
    type: z
      .enum(["user", "feedback", "project", "reference"])
      .optional()
      .describe("Filter by type"),
    limit: z.number().default(20).describe("Max results"),
  },
  async ({ type, limit }) => {
    const rows = type
      ? stmts.listByType.all(type, limit)
      : stmts.listAll.all(limit);
    if (rows.length === 0) {
      return { content: [{ type: "text", text: "No memories stored yet." }] };
    }
    const text = rows
      .map((r) => `#${r.id} [${r.type}] ${r.name} — ${r.preview}...`)
      .join("\n");
    return { content: [{ type: "text", text }] };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
