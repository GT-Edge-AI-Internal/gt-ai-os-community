"""
Default Model Configurations for GT 2.0

This module contains the default configuration for all 19 Groq models
plus the BGE-M3 embedding model on GT Edge network.
"""

from typing import List, Dict, Any


def get_default_models() -> List[Dict[str, Any]]:
    """Get list of all default model configurations"""
    
    # Groq LLM Models (11 models)
    groq_llm_models = [
        {
            "model_id": "llama-3.3-70b-versatile",
            "name": "Llama 3.3 70B Versatile",
            "version": "3.3",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 128000,
                "max_tokens": 32768,
            },
            "capabilities": {
                "reasoning": True,
                "function_calling": True,
                "streaming": True,
                "multilingual": True
            },
            "cost": {
                "per_1k_input": 0.59,
                "per_1k_output": 0.79
            },
            "description": "Latest Llama 3.3 70B model optimized for versatile tasks with large context window",
            "is_active": True
        },
        {
            "model_id": "llama-3.3-70b-specdec",
            "name": "Llama 3.3 70B Speculative Decoding",
            "version": "3.3",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 8192,
                "max_tokens": 8192,
            },
            "capabilities": {
                "reasoning": True,
                "function_calling": True,
                "streaming": True
            },
            "cost": {
                "per_1k_input": 0.59,
                "per_1k_output": 0.79
            },
            "description": "Llama 3.3 70B with speculative decoding for faster inference",
            "is_active": True
        },
        {
            "model_id": "llama-3.2-90b-text-preview",
            "name": "Llama 3.2 90B Text Preview",
            "version": "3.2",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 128000,
                "max_tokens": 8000,
            },
            "capabilities": {
                "reasoning": True,
                "function_calling": True,
                "streaming": True
            },
            "cost": {
                "per_1k_input": 0.2,
                "per_1k_output": 0.2
            },
            "description": "Large Llama 3.2 model with enhanced text processing capabilities",
            "is_active": True
        },
        {
            "model_id": "llama-3.1-405b-reasoning",
            "name": "Llama 3.1 405B Reasoning",
            "version": "3.1",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 131072,
                "max_tokens": 32768,
            },
            "capabilities": {
                "reasoning": True,
                "function_calling": True,
                "streaming": True,
                "multilingual": True
            },
            "cost": {
                "per_1k_input": 2.5,
                "per_1k_output": 2.5
            },
            "description": "Largest Llama model optimized for complex reasoning tasks",
            "is_active": True
        },
        {
            "model_id": "llama-3.1-70b-versatile",
            "name": "Llama 3.1 70B Versatile",
            "version": "3.1",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 131072,
                "max_tokens": 32768,
            },
            "capabilities": {
                "reasoning": True,
                "function_calling": True,
                "streaming": True,
                "multilingual": True
            },
            "cost": {
                "per_1k_input": 0.59,
                "per_1k_output": 0.79
            },
            "description": "Balanced Llama model for general-purpose tasks with large context",
            "is_active": True
        },
        {
            "model_id": "llama-3.1-8b-instant",
            "name": "Llama 3.1 8B Instant",
            "version": "3.1",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 131072,
                "max_tokens": 8192,
            },
            "capabilities": {
                "streaming": True,
                "multilingual": True
            },
            "cost": {
                "per_1k_input": 0.05,
                "per_1k_output": 0.08
            },
            "description": "Fast and efficient Llama model for quick responses",
            "is_active": True
        },
        {
            "model_id": "llama3-groq-70b-8192-tool-use-preview",
            "name": "Llama 3 Groq 70B Tool Use Preview",
            "version": "3.0",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 8192,
                "max_tokens": 8192,
            },
            "capabilities": {
                "function_calling": True,
                "streaming": True
            },
            "cost": {
                "per_1k_input": 0.89,
                "per_1k_output": 0.89
            },
            "description": "Llama 3 70B optimized for tool use and function calling",
            "is_active": True
        },
        {
            "model_id": "llama3-groq-8b-8192-tool-use-preview",
            "name": "Llama 3 Groq 8B Tool Use Preview",
            "version": "3.0",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 8192,
                "max_tokens": 8192,
            },
            "capabilities": {
                "function_calling": True,
                "streaming": True
            },
            "cost": {
                "per_1k_input": 0.19,
                "per_1k_output": 0.19
            },
            "description": "Compact Llama 3 model optimized for tool use and function calling",
            "is_active": True
        },
        {
            "model_id": "mixtral-8x7b-32768",
            "name": "Mixtral 8x7B",
            "version": "1.0",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 32768,
                "max_tokens": 32768,
            },
            "capabilities": {
                "reasoning": True,
                "streaming": True,
                "multilingual": True
            },
            "cost": {
                "per_1k_input": 0.24,
                "per_1k_output": 0.24
            },
            "description": "Mixture of experts model with strong multilingual capabilities",
            "is_active": True
        },
        {
            "model_id": "gemma2-9b-it",
            "name": "Gemma 2 9B Instruction Tuned",
            "version": "2.0",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 8192,
                "max_tokens": 8192,
            },
            "capabilities": {
                "streaming": True,
                "multilingual": False
            },
            "cost": {
                "per_1k_input": 0.2,
                "per_1k_output": 0.2
            },
            "description": "Google's Gemma 2 model optimized for instruction following",
            "is_active": True
        },
        {
            "model_id": "llama-guard-3-8b",
            "name": "Llama Guard 3 8B",
            "version": "3.0",
            "provider": "groq",
            "model_type": "llm",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "specifications": {
                "context_window": 8192,
                "max_tokens": 8192,
            },
            "capabilities": {
                "streaming": False,
                "safety_classification": True
            },
            "cost": {
                "per_1k_input": 0.2,
                "per_1k_output": 0.2
            },
            "description": "Safety classification model for content moderation",
            "is_active": True
        }
    ]
    
    # Groq Audio Models (3 models)
    groq_audio_models = [
        {
            "model_id": "whisper-large-v3",
            "name": "Whisper Large v3",
            "version": "3.0",
            "provider": "groq",
            "model_type": "audio",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "capabilities": {
                "transcription": True,
                "multilingual": True
            },
            "cost": {
                "per_1k_input": 0.111,
                "per_1k_output": 0.111
            },
            "description": "High-quality speech transcription with multilingual support",
            "is_active": True
        },
        {
            "model_id": "whisper-large-v3-turbo",
            "name": "Whisper Large v3 Turbo",
            "version": "3.0",
            "provider": "groq",
            "model_type": "audio",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "capabilities": {
                "transcription": True,
                "multilingual": True
            },
            "cost": {
                "per_1k_input": 0.04,
                "per_1k_output": 0.04
            },
            "description": "Fast speech transcription optimized for speed",
            "is_active": True
        },
        {
            "model_id": "distil-whisper-large-v3-en",
            "name": "Distil-Whisper Large v3 English",
            "version": "3.0",
            "provider": "groq",
            "model_type": "audio",
            "endpoint": "https://api.groq.com/openai/v1",
            "api_key_name": "GROQ_API_KEY",
            "capabilities": {
                "transcription": True,
                "multilingual": False
            },
            "cost": {
                "per_1k_input": 0.02,
                "per_1k_output": 0.02
            },
            "description": "Compact English-only transcription model",
            "is_active": True
        }
    ]
    
    # BGE-M3 Embedding Model (External on GT Edge)
    external_models = [
        {
            "model_id": "bge-m3",
            "name": "BAAI BGE-M3 Multilingual Embeddings",
            "version": "1.0",
            "provider": "external",
            "model_type": "embedding",
            "endpoint": "http://10.0.1.50:8080",  # GT Edge local network
            "specifications": {
                "dimensions": 1024,
                "max_tokens": 8192,
            },
            "capabilities": {
                "multilingual": True,
                "dense_retrieval": True,
                "sparse_retrieval": True,
                "colbert": True
            },
            "cost": {
                "per_1k_input": 0.0,
                "per_1k_output": 0.0
            },
            "description": "State-of-the-art multilingual embedding model running on GT Edge local network",
            "config": {
                "batch_size": 32,
                "normalize": True,
                "pooling_method": "mean"
            },
            "is_active": True
        }
    ]
    
    # Local Ollama Models (for on-premise deployments)
    ollama_models = [
        {
            "model_id": "ollama-local-dgx-x86",
            "name": "Local Ollama (DGX/X86)",
            "version": "1.0",
            "provider": "ollama",
            "model_type": "llm",
            "endpoint": "http://ollama-host:11434/v1/chat/completions",
            "api_key_name": None,  # No API key needed for local Ollama
            "specifications": {
                "context_window": 131072,
                "max_tokens": 4096,
            },
            "capabilities": {
                "streaming": True,
                "function_calling": False
            },
            "cost": {
                "per_1k_input": 0.0,
                "per_1k_output": 0.0
            },
            "description": "Local Ollama instance for DGX and x86 Linux deployments. Uses ollama-host DNS resolution.",
            "is_active": True
        },
        {
            "model_id": "ollama-local-macos",
            "name": "Local Ollama (MacOS)",
            "version": "1.0",
            "provider": "ollama",
            "model_type": "llm",
            "endpoint": "http://host.docker.internal:11434/v1/chat/completions",
            "api_key_name": None,  # No API key needed for local Ollama
            "specifications": {
                "context_window": 131072,
                "max_tokens": 4096,
            },
            "capabilities": {
                "streaming": True,
                "function_calling": False
            },
            "cost": {
                "per_1k_input": 0.0,
                "per_1k_output": 0.0
            },
            "description": "Local Ollama instance for macOS deployments. Uses host.docker.internal for Docker-to-host networking.",
            "is_active": True
        }
    ]

    # TTS Models (placeholder - will be added when available)
    tts_models = [
        # Future TTS models from Groq/PlayAI
    ]

    # Combine all models
    all_models = groq_llm_models + groq_audio_models + external_models + ollama_models + tts_models
    
    return all_models


def get_groq_models() -> List[Dict[str, Any]]:
    """Get only Groq models"""
    return [model for model in get_default_models() if model["provider"] == "groq"]


def get_external_models() -> List[Dict[str, Any]]:
    """Get only external models (BGE-M3, etc.)"""
    return [model for model in get_default_models() if model["provider"] == "external"]


def get_ollama_models() -> List[Dict[str, Any]]:
    """Get only Ollama models (local inference)"""
    return [model for model in get_default_models() if model["provider"] == "ollama"]


def get_models_by_type(model_type: str) -> List[Dict[str, Any]]:
    """Get models by type (llm, embedding, audio, tts)"""
    return [model for model in get_default_models() if model["model_type"] == model_type]