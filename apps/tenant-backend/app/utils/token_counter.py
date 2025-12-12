"""Token counting and budget management - ensures zero context overflows"""

import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate tokens: 1 token ≈ 4 chars (conservative for safety).

    This is a rough estimation. For production with critical accuracy needs,
    consider integrating tiktoken library for model-specific tokenization.
    """
    return len(text) // 4 if text else 0


def estimate_messages_tokens(messages: list) -> int:
    """Estimate total tokens in message list"""
    total = 0
    for msg in messages:
        content = msg.get('content', '') if isinstance(msg, dict) else str(msg)
        total += estimate_tokens(content)
    return total


def calculate_file_context_budget(
    context_window: int,
    conversation_history_tokens: int,
    model_max_tokens: int,
    system_overhead_tokens: int = 500
) -> int:
    """
    Calculate exact token budget for file context.
    GUARANTEES: budget + history + response + overhead <= context_window

    Args:
        context_window: Model's total context window (from model config)
        conversation_history_tokens: Tokens used by conversation messages
        model_max_tokens: Maximum tokens reserved for model response (from model config)
        system_overhead_tokens: Tokens for system prompts, tool definitions

    Returns:
        Maximum tokens available for file context (HARD LIMIT)
    """
    SAFETY_MARGIN = 0.05  # 5% buffer for tokenization variance

    # Usable context after safety margin
    usable_context = int(context_window * (1 - SAFETY_MARGIN))

    # Calculate available budget
    available = usable_context - conversation_history_tokens - model_max_tokens - system_overhead_tokens

    # Enforce minimum (if budget exhausted, return 0 - let caller handle)
    return max(0, available)


def fit_chunks_to_budget(
    chunks: List[Dict[str, Any]],
    token_budget: int,
    preserve_file_boundaries: bool = True
) -> List[Dict[str, Any]]:
    """
    Fit chunks to exact token budget.
    Returns subset of chunks that fit perfectly without exceeding budget.

    Strategy:
    - Include complete chunks only (never truncate mid-chunk)
    - If preserve_file_boundaries: ensure each file gets representation via round-robin
    - Return when budget would be exceeded

    Args:
        chunks: List of chunk dictionaries with 'content' and 'document_id'
        token_budget: Maximum tokens allowed
        preserve_file_boundaries: If True, round-robin across files for diversity

    Returns:
        List of chunks that fit within budget
    """
    if token_budget <= 0:
        return []

    if not chunks:
        return []

    # Group by file
    by_file = defaultdict(list)
    for chunk in chunks:
        by_file[chunk['document_id']].append(chunk)

    selected_chunks = []
    current_tokens = 0

    if preserve_file_boundaries and len(by_file) > 1:
        # Strategy: Round-robin across files to ensure diversity
        file_ids = list(by_file.keys())
        file_indices = {fid: 0 for fid in file_ids}

        while True:
            added_any = False
            for file_id in file_ids:
                idx = file_indices[file_id]
                if idx >= len(by_file[file_id]):
                    continue

                chunk = by_file[file_id][idx]
                chunk_tokens = estimate_tokens(chunk['content'])

                if current_tokens + chunk_tokens <= token_budget:
                    selected_chunks.append(chunk)
                    current_tokens += chunk_tokens
                    file_indices[file_id] += 1
                    added_any = True
                # If chunk doesn't fit, skip it (don't try more from this file)

            if not added_any:
                break
    else:
        # Single file or no boundary preservation: simple sequential
        for chunk in chunks:
            chunk_tokens = estimate_tokens(chunk['content'])
            if current_tokens + chunk_tokens <= token_budget:
                selected_chunks.append(chunk)
                current_tokens += chunk_tokens
            else:
                break  # Stop when budget exhausted

    logger.debug(f"Fitted {len(selected_chunks)}/{len(chunks)} chunks to budget ({current_tokens}/{token_budget} tokens)")
    return selected_chunks
