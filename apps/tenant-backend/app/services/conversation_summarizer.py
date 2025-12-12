"""
Conversation Summarization Service for GT 2.0

Automatically generates meaningful conversation titles using a specialized 
summarization agent with llama-3.1-8b-instant.
"""

import json
import logging
from typing import List, Optional, Dict, Any

from app.core.config import get_settings
from app.core.resource_client import ResourceClusterClient

logger = logging.getLogger(__name__)
settings = get_settings()


class ConversationSummarizer:
    """Service for generating conversation summaries and titles"""
    
    def __init__(self, tenant_id: str, user_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.resource_client = ResourceClusterClient()
        self.summarization_model = "llama-3.1-8b-instant"
        
    async def generate_conversation_title(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate a concise conversation title based on the conversation content.
        
        Args:
            messages: List of message dictionaries from the conversation
            
        Returns:
            Generated conversation title (3-6 words)
        """
        try:
            # Extract conversation context for summarization
            conversation_text = self._prepare_conversation_context(messages)
            
            if not conversation_text.strip():
                return "New Conversation"
            
            # Generate title using specialized summarization prompt
            title = await self._call_summarization_agent(conversation_text)
            
            # Validate and clean the generated title
            clean_title = self._clean_title(title)
            
            logger.info(f"Generated conversation title: '{clean_title}' from {len(messages)} messages")
            return clean_title
            
        except Exception as e:
            logger.error(f"Error generating conversation title: {e}")
            return self._fallback_title(messages)
    
    def _prepare_conversation_context(self, messages: List[Dict[str, Any]]) -> str:
        """Prepare conversation context for summarization"""
        if not messages:
            return ""
            
        # Limit to first few exchanges for title generation
        context_messages = messages[:6]  # First 3 user-agent exchanges
        
        context_parts = []
        for msg in context_messages:
            role = "User" if msg.get("role") == "user" else "Agent"
            # Truncate very long messages for context
            content = msg.get("content", "")
            content = content[:200] + "..." if len(content) > 200 else content
            context_parts.append(f"{role}: {content}")
            
        return "\n".join(context_parts)
    
    async def _call_summarization_agent(self, conversation_text: str) -> str:
        """Call the resource cluster AI inference for summarization"""
        
        summarization_prompt = f"""You are a conversation title generator. Your job is to create concise, descriptive titles for conversations.

Given this conversation:
---
{conversation_text}
---

Generate a title that:
- Is 3-6 words maximum
- Captures the main topic or purpose
- Is clear and descriptive
- Uses title case
- Does NOT include quotes or special characters

Examples of good titles:
- "Python Code Review"
- "Database Migration Help"
- "React Component Design"
- "System Architecture Discussion"

Title:"""

        request_data = {
            "messages": [
                {
                    "role": "user",
                    "content": summarization_prompt
                }
            ],
            "model": self.summarization_model,
            "temperature": 0.3,  # Lower temperature for consistent, focused titles
            "max_tokens": 20,    # Short response for title generation
            "stream": False
        }
        
        try:
            # Use the resource client instead of direct HTTP calls
            result = await self.resource_client.call_inference_endpoint(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                endpoint="chat/completions",
                data=request_data
            )
            
            if result and "choices" in result and len(result["choices"]) > 0:
                title = result["choices"][0]["message"]["content"].strip()
                return title
            else:
                logger.error("Invalid response format from summarization API")
                return ""
                        
        except Exception as e:
            logger.error(f"Error calling summarization agent: {e}")
            return ""
    
    def _clean_title(self, raw_title: str) -> str:
        """Clean and validate the generated title"""
        if not raw_title:
            return "New Conversation"
            
        # Remove quotes, extra whitespace, and special characters
        cleaned = raw_title.strip().strip('"\'').strip()
        
        # Remove common prefixes that AI might add
        prefixes_to_remove = [
            "Title:", "title:", "TITLE:",
            "Conversation:", "conversation:",
            "Topic:", "topic:",
            "Subject:", "subject:"
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        # Limit length and ensure it's reasonable
        if len(cleaned) > 50:
            cleaned = cleaned[:47] + "..."
        
        # Ensure it's not empty after cleaning
        if not cleaned or len(cleaned.split()) > 8:
            return "New Conversation"
            
        return cleaned
    
    def _fallback_title(self, messages: List[Dict[str, Any]]) -> str:
        """Generate fallback title when AI summarization fails"""
        if not messages:
            return "New Conversation"
            
        # Try to use the first user message for context
        first_user_msg = next((msg for msg in messages if msg.get("role") == "user"), None)
        
        if first_user_msg and first_user_msg.get("content"):
            # Extract first few words from the user's message
            words = first_user_msg["content"].strip().split()[:4]
            if len(words) >= 2:
                fallback = " ".join(words).capitalize()
                # Remove common question words for cleaner titles
                for word in ["How", "What", "Can", "Could", "Please", "Help"]:
                    if fallback.startswith(word + " "):
                        fallback = fallback[len(word):].strip()
                        break
                return fallback if fallback else "New Conversation"
        
        return "New Conversation"


async def generate_conversation_title(messages: List[Dict[str, Any]], tenant_id: str, user_id: str) -> str:
    """
    Convenience function to generate a conversation title.
    
    Args:
        messages: List of message dictionaries from the conversation
        tenant_id: Tenant identifier
        user_id: User identifier
        
    Returns:
        Generated conversation title
    """
    summarizer = ConversationSummarizer(tenant_id, user_id)
    return await summarizer.generate_conversation_title(messages)