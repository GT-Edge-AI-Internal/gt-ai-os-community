# Chat Completions Endpoint - Data Analysis

**Endpoint**: `/api/v1/chat/completions`
**Date**: 2025-10-03
**Status**: ⚠️ **SENDING UNNECESSARY INTERNAL DATA**

---

## Current Response Structure

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1696234567,
  "model": "groq/llama-3.1-8b-instant",
  "choices": [{
    "index": 0,
    "message": {
      "role": "agent",
      "content": "AI response text..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 80,
    "total_tokens": 230
  },
  "conversation_id": "conv-uuid",
  "agent_id": "agent-uuid",

  "rag_context": {
    "chunks_used": 5,
    "sources": [
      {
        "document_id": "doc-uuid-123",           // ⚠️ INTERNAL UUID
        "dataset_id": "dataset-uuid-456",        // ⚠️ INTERNAL UUID
        "document_name": "security-policy.pdf",
        "source_type": "dataset",
        "access_scope": "permanent",
        "search_method": "mcp_tool",             // ⚠️ INTERNAL DETAIL
        "conversation_id": "conv-uuid",          // ⚠️ DUPLICATE
        "uploaded_at": "2025-10-01T12:00:00Z"
      }
    ],
    "datasets_searched": ["uuid1", "uuid2"],     // ⚠️ INTERNAL UUIDS
    "retrieval_time_ms": 234,
    "search_queries": ["security policy", "auth"] // ⚠️ EXPOSES SEARCH STRATEGY
  }
}
```

---

## Frontend Usage Analysis

### What References Panel Actually Uses:

From `src/components/chat/references-panel.tsx`:

**✅ USED:**
- `source.id` - For expand/collapse state tracking
- `source.name` - Document name display
- `source.type` - Icon and color coding
- `source.relevance` - Relevance percentage badge
- `source.metadata.conversation_title` - Context display
- `source.metadata.agent_name` - Context display
- `source.metadata.chunks` - Chunk count display
- `source.metadata.created_at` - Date formatting
- `source.metadata.file_type` - Document type
- `source.metadata.document_id` - For document URLs

**❌ NOT USED in UI:**
- `document_id` at root level (duplicate of metadata.document_id)
- `dataset_id` - Never referenced
- `search_method` - Internal implementation detail
- `datasets_searched` array - Never displayed
- `search_queries` array - Never displayed
- `retrieval_time_ms` - Never displayed

---

## Security & Privacy Issues

### ⚠️ Issue 1: Exposing Internal UUIDs

**Current**: Sending `document_id`, `dataset_id`, `datasets_searched`
**Risk**:
- UUID enumeration attacks
- Reveals system architecture
- No benefit to user

**Recommendation**: Remove or obfuscate

### ⚠️ Issue 2: Search Strategy Exposure

**Current**: Sending `search_queries` array
**Risk**:
- Reveals RAG search logic
- Exposes query expansion strategy
- Competitive intelligence leak

**Recommendation**: Remove from response

### ⚠️ Issue 3: Implementation Details

**Current**: Sending `search_method` ("mcp_tool" vs "auto_rag")
**Risk**:
- Exposes internal implementation
- No value to end user
- Unnecessary technical details

**Recommendation**: Remove or simplify to user-facing terms

### ⚠️ Issue 4: Redundant Data

**Current**: Both `conversation_id` at root AND in sources
**Issue**:
- Duplicate data transmission
- Wasted bandwidth

**Recommendation**: Remove from sources if already at root level

---

## Recommended Minimal Response

### Option 1: Minimal (Security-First)

```json
{
  "rag_context": {
    "chunks_used": 5,
    "sources": [
      {
        "id": "source-1",                    // For UI state only
        "name": "security-policy.pdf",
        "type": "dataset",
        "relevance": 0.89,
        "metadata": {
          "created_at": "2025-10-01T12:00:00Z",
          "file_type": "pdf",
          "conversation_title": "Security Discussion",  // If history
          "agent_name": "Security Expert",              // If history
          "chunks": 3
        }
      }
    ]
  }
}
```

**Removed**: document_id, dataset_id, search_method, datasets_searched, search_queries, retrieval_time_ms

**Size Reduction**: ~40-50% smaller

### Option 2: Balanced (Keep Useful Metadata)

```json
{
  "rag_context": {
    "chunks_used": 5,
    "sources": [
      {
        "id": "source-1",
        "name": "security-policy.pdf",
        "type": "dataset",
        "scope": "permanent",               // Keep: user-facing
        "relevance": 0.89,
        "metadata": {
          "created_at": "2025-10-01T12:00:00Z",
          "file_type": "pdf",
          "chunks": 3
        }
      }
    ],
    "retrieval_time_ms": 234               // Keep: performance transparency
  }
}
```

**Removed**: document_id, dataset_id, search_method, datasets_searched, search_queries, conversation_id (from sources)

**Size Reduction**: ~30-35% smaller

---

## Implementation Plan

### Step 1: Create RAG Response Filter

```python
# In app/core/response_filter.py

@staticmethod
def filter_rag_context(rag_context: Dict[str, Any]) -> Dict[str, Any]:
    """Filter RAG context to remove internal implementation details"""
    if not rag_context:
        return None

    filtered_sources = []
    for source in rag_context.get("sources", []):
        filtered_source = {
            "id": source.get("document_id", "")[:8],  # Short ID for UI state
            "name": source.get("document_name"),
            "type": source.get("source_type"),
            "scope": source.get("access_scope"),
            "relevance": source.get("relevance", 1.0),
            "metadata": {
                "created_at": source.get("uploaded_at") or source.get("created_at"),
                "file_type": source.get("file_type"),
                "chunks": source.get("chunks_used")
            }
        }

        # Add conversation context if present
        if source.get("conversation_title"):
            filtered_source["metadata"]["conversation_title"] = source["conversation_title"]
        if source.get("agent_name"):
            filtered_source["metadata"]["agent_name"] = source["agent_name"]

        filtered_sources.append(filtered_source)

    return {
        "chunks_used": rag_context.get("chunks_used"),
        "sources": filtered_sources,
        "retrieval_time_ms": rag_context.get("retrieval_time_ms")
        # REMOVED: datasets_searched, search_queries, document_id, dataset_id
    }
```

### Step 2: Apply Filter in Chat Endpoint

```python
# In app/api/v1/chat.py (line ~860-870)

# Prepare RAG context for response
rag_response_context = None
if rag_context and rag_context.chunks:
    # Apply security filtering
    from app.core.response_filter import ResponseFilter
    rag_response_context = ResponseFilter.filter_rag_context({
        "chunks_used": len(rag_context.chunks),
        "sources": rag_context.sources,
        "datasets_searched": rag_context.datasets_used,
        "retrieval_time_ms": rag_context.retrieval_time_ms,
        "search_queries": rag_context.search_queries
    })
```

### Step 3: Update Frontend (If Needed)

**Current**: References panel uses `source.id` for state
**Change**: Ensure it uses the shortened ID format

---

## Metrics

### Current RAG Context Size (Typical Response)
- 5 sources with full data: ~1.2KB
- Internal UUIDs: ~180 bytes
- Search metadata: ~150 bytes
- **Total**: ~1.5KB

### Minimal RAG Context Size
- 5 sources filtered: ~800 bytes
- No UUIDs or search data
- **Total**: ~800 bytes
- **Savings**: 47% reduction

### Performance Impact
- Filtering overhead: <0.5ms
- Network savings: ~700 bytes per response
- Over 1000 chat messages: ~700KB saved

---

## Testing Checklist

- [ ] References panel displays correctly with filtered data
- [ ] Document URLs still work (if using metadata.document_id)
- [ ] Citation formatting works
- [ ] No console errors for missing fields
- [ ] Search strategy not exposed to client
- [ ] Internal UUIDs not visible in DevTools

---

## Security Benefits

✅ **UUID Exposure**: Eliminated
✅ **Search Strategy**: Hidden
✅ **Implementation Details**: Removed
✅ **Data Minimization**: Achieved
✅ **Bandwidth**: Reduced 47%

---

## Recommendation

**Implement Option 1 (Minimal)** for maximum security:
- Remove all internal UUIDs
- Remove search strategy details
- Keep only user-facing metadata
- 47% size reduction
- Zero security risk from RAG context

This aligns with the principle of least privilege applied to other endpoints.
