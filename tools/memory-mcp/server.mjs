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

db.exec(`
  CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('user','feedback','project','reference')),
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
  CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    name, content, content=memories, content_rowid=id
  );
`);

// Recreate triggers (CREATE TRIGGER IF NOT EXISTS not supported in all SQLite FTS5 builds)
const triggerExists = db
  .prepare("SELECT name FROM sqlite_master WHERE type='trigger' AND name='memories_ai'")
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
  listByType: db.prepare(
    "SELECT id, type, name, substr(content, 1, 120) AS preview, created_at, updated_at FROM memories WHERE type = ? ORDER BY updated_at DESC LIMIT ?"
  ),
  listAll: db.prepare(
    "SELECT id, type, name, substr(content, 1, 120) AS preview, created_at, updated_at FROM memories ORDER BY updated_at DESC LIMIT ?"
  ),
  getById: db.prepare("SELECT * FROM memories WHERE id = ?"),
};

const server = new McpServer({
  name: "memory",
  version: "1.0.0",
});

server.tool(
  "remember",
  "Save a memory to the knowledge base. Use this to persist useful information across conversations.",
  {
    type: z.enum(["user", "feedback", "project", "reference"]).describe(
      "user=about the user, feedback=user corrections, project=project context, reference=external pointers"
    ),
    name: z.string().describe("Short descriptive name for this memory"),
    content: z.string().describe("The memory content to store"),
  },
  async ({ type, name, content }) => {
    const result = stmts.insert.run(type, name, content);
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
  "Search memories by keyword. Returns the most relevant matches using full-text search.",
  {
    query: z.string().describe("Search query (supports FTS5 syntax: AND, OR, NOT, prefix*)"),
    type: z.enum(["user", "feedback", "project", "reference"]).optional().describe("Filter by memory type"),
    limit: z.number().default(10).describe("Max results to return"),
  },
  async ({ query, type, limit }) => {
    const rows = type
      ? stmts.searchByType.all(query, type, limit)
      : stmts.search.all(query, limit);
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
        { type: "text", text: `Deleted memory #${id}: [${row.type}] ${row.name}` },
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
    content: z.string().optional().describe("New content (omit to keep current)"),
  },
  async ({ id, name, content }) => {
    const row = stmts.getById.get(id);
    if (!row) {
      return { content: [{ type: "text", text: `Memory #${id} not found.` }] };
    }
    stmts.update.run(name ?? row.name, content ?? row.content, id);
    return {
      content: [
        { type: "text", text: `Updated memory #${id}: [${row.type}] ${name ?? row.name}` },
      ],
    };
  }
);

server.tool(
  "list_memories",
  "List all stored memories, optionally filtered by type.",
  {
    type: z.enum(["user", "feedback", "project", "reference"]).optional().describe("Filter by type"),
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
