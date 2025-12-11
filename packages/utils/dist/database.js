"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getTenantDatabasePath = getTenantDatabasePath;
exports.getTenantChromaCollection = getTenantChromaCollection;
exports.getTenantRedisPrefix = getTenantRedisPrefix;
exports.getTenantMinioBucket = getTenantMinioBucket;
exports.getSQLiteWALConfig = getSQLiteWALConfig;
exports.getSQLiteEncryptionConfig = getSQLiteEncryptionConfig;
exports.getTenantDatabaseSchema = getTenantDatabaseSchema;
exports.generateDocumentChunkId = generateDocumentChunkId;
exports.parseConnectionString = parseConnectionString;
exports.escapeSQLIdentifier = escapeSQLIdentifier;
exports.generateBackupFilename = generateBackupFilename;
// Database utility functions
const path_1 = __importDefault(require("path"));
const crypto_1 = __importDefault(require("crypto"));
/**
 * Generate SQLite database path for tenant
 */
function getTenantDatabasePath(tenantDomain, dataDir = '/data') {
    return path_1.default.join(dataDir, tenantDomain, 'app.db');
}
/**
 * Generate ChromaDB collection name for tenant
 */
function getTenantChromaCollection(tenantDomain) {
    // ChromaDB collection names must be alphanumeric with underscores
    return `gt2_${tenantDomain.replace(/-/g, '_')}_documents`;
}
/**
 * Generate Redis key prefix for tenant
 */
function getTenantRedisPrefix(tenantDomain) {
    return `gt2:${tenantDomain}:`;
}
/**
 * Generate MinIO bucket name for tenant
 */
function getTenantMinioBucket(tenantDomain) {
    // MinIO bucket names must be lowercase and DNS-compliant
    return `gt2-${tenantDomain}-files`;
}
/**
 * Generate SQLite WAL mode configuration
 */
function getSQLiteWALConfig() {
    return `
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    PRAGMA cache_size=1000;
    PRAGMA foreign_keys=ON;
    PRAGMA temp_store=MEMORY;
  `;
}
/**
 * Generate SQLite encryption configuration
 */
function getSQLiteEncryptionConfig(encryptionKey) {
    return `PRAGMA key='${encryptionKey}';`;
}
/**
 * Create tenant database schema (SQLite)
 */
function getTenantDatabaseSchema() {
    return `
    -- Enable foreign key constraints
    PRAGMA foreign_keys = ON;

    -- Conversations for AI chat
    CREATE TABLE IF NOT EXISTS conversations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      model_id TEXT NOT NULL,
      system_prompt TEXT,
      created_by TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Messages with full context tracking
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
      role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
      content TEXT NOT NULL,
      model_used TEXT,
      tokens_used INTEGER DEFAULT 0,
      context_sources TEXT DEFAULT '[]', -- JSON array of document chunk IDs
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Documents with processing status
    CREATE TABLE IF NOT EXISTS documents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      filename TEXT NOT NULL,
      file_type TEXT NOT NULL,
      file_size INTEGER DEFAULT 0,
      processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
      chunk_count INTEGER DEFAULT 0,
      uploaded_by TEXT NOT NULL,
      storage_path TEXT,
      error_message TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Document chunks for RAG
    CREATE TABLE IF NOT EXISTS document_chunks (
      id TEXT PRIMARY KEY, -- UUID
      document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      chunk_index INTEGER NOT NULL,
      content TEXT NOT NULL,
      metadata TEXT DEFAULT '{}', -- JSON metadata
      embedding_id TEXT, -- Reference to ChromaDB embedding
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- User sessions and preferences
    CREATE TABLE IF NOT EXISTS user_sessions (
      id TEXT PRIMARY KEY, -- Session token
      user_email TEXT NOT NULL,
      expires_at DATETIME NOT NULL,
      data TEXT DEFAULT '{}', -- JSON session data
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- User preferences
    CREATE TABLE IF NOT EXISTS user_preferences (
      user_email TEXT PRIMARY KEY,
      preferences TEXT DEFAULT '{}', -- JSON preferences
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Usage tracking for tenant
    CREATE TABLE IF NOT EXISTS usage_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_email TEXT NOT NULL,
      action_type TEXT NOT NULL, -- 'chat', 'document_upload', 'document_query'
      resource_used TEXT, -- Model name or resource identifier
      tokens_used INTEGER DEFAULT 0,
      success BOOLEAN DEFAULT TRUE,
      metadata TEXT DEFAULT '{}', -- JSON metadata
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_conversations_created_by ON conversations(created_by);
    CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at);
    CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
    CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by);
    CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
    CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
    CREATE INDEX IF NOT EXISTS idx_usage_logs_user_email ON usage_logs(user_email);
    CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at);
    CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

    -- Triggers for updated_at columns
    CREATE TRIGGER IF NOT EXISTS update_conversations_updated_at 
    AFTER UPDATE ON conversations
    BEGIN
      UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

    CREATE TRIGGER IF NOT EXISTS update_documents_updated_at 
    AFTER UPDATE ON documents
    BEGIN
      UPDATE documents SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

    CREATE TRIGGER IF NOT EXISTS update_user_preferences_updated_at 
    AFTER UPDATE ON user_preferences
    BEGIN
      UPDATE user_preferences SET updated_at = CURRENT_TIMESTAMP WHERE user_email = NEW.user_email;
    END;
  `;
}
/**
 * Generate unique document chunk ID
 */
function generateDocumentChunkId(documentId, chunkIndex) {
    const data = `${documentId}-${chunkIndex}-${Date.now()}`;
    return crypto_1.default.createHash('sha256').update(data).digest('hex').substring(0, 32);
}
/**
 * Parse connection string for database configuration
 */
function parseConnectionString(connectionString) {
    const url = new URL(connectionString);
    return {
        host: url.hostname,
        port: url.port ? parseInt(url.port) : undefined,
        database: url.pathname.substring(1), // Remove leading slash
        username: url.username,
        password: url.password,
        options: Object.fromEntries(url.searchParams.entries())
    };
}
/**
 * Escape SQL identifiers (table names, column names, etc.)
 */
function escapeSQLIdentifier(identifier) {
    return `"${identifier.replace(/"/g, '""')}"`;
}
/**
 * Generate database backup filename
 */
function generateBackupFilename(tenantDomain, timestamp) {
    const date = timestamp || new Date();
    const dateString = date.toISOString().split('T')[0]; // YYYY-MM-DD
    const timeString = date.toTimeString().split(' ')[0].replace(/:/g, '-'); // HH-MM-SS
    return `gt2-${tenantDomain}-backup-${dateString}-${timeString}.db`;
}
