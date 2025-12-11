#!/usr/bin/env python3
"""
OpenAI-Compatible BGE-M3 Embedding Server for GT 2.0
Provides real BGE-M3 embeddings via OpenAI-compatible API - NO FALLBACKS
"""

import asyncio
import logging
import time
import uvicorn
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BGE-M3 Model with ONNX Runtime optimization
from sentence_transformers import SentenceTransformer
import torch
import os
import numpy as np

# ONNX Runtime imports with direct session support
try:
    import onnxruntime as ort
    from transformers import AutoTokenizer
    ONNX_AVAILABLE = True
    logger.info("ONNX Runtime available for ARM64 optimization")
except ImportError as e:
    ONNX_AVAILABLE = False
    logger.warning(f"ONNX Runtime not available, falling back to SentenceTransformers: {e}")

# Global model instances
model = None
tokenizer = None
onnx_session = None
use_onnx = False
model_mode = "unknown"

def mean_pooling(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """
    Perform mean pooling on token embeddings using attention mask.

    Args:
        token_embeddings: Token-level embeddings [batch_size, seq_len, hidden_dim]
        attention_mask: Attention mask [batch_size, seq_len]

    Returns:
        Pooled embeddings [batch_size, hidden_dim]
    """
    # Expand attention mask to match embeddings dimensions
    attention_mask_expanded = np.expand_dims(attention_mask, -1)

    # Sum embeddings where attention mask is 1
    sum_embeddings = np.sum(token_embeddings * attention_mask_expanded, axis=1)

    # Sum attention mask to get actual sequence lengths
    sum_mask = np.sum(attention_mask_expanded, axis=1)

    # Divide to get mean (avoid division by zero)
    mean_embeddings = sum_embeddings / np.maximum(sum_mask, 1e-9)

    return mean_embeddings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load BGE-M3 model on startup with ONNX optimization"""
    global model, tokenizer, onnx_session, use_onnx, model_mode
    logger.info("Loading BGE-M3 model with ARM64 optimization...")

    # Check if ONNX Runtime should be used
    use_onnx_env = os.getenv('USE_ONNX_RUNTIME', 'true').lower() == 'true'

    try:
        if ONNX_AVAILABLE and use_onnx_env:
            # Try ONNX Runtime with direct session for maximum ARM64 performance
            logger.info("Attempting to load BGE-M3 with direct ONNX Runtime session...")
            try:
                # Load tokenizer
                tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-m3')

                # Check for cached ONNX model
                cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
                model_id = 'models--BAAI--bge-m3'

                # Find ONNX model in cache
                import glob
                onnx_pattern = f'{cache_dir}/{model_id}/snapshots/*/onnx/model.onnx'
                onnx_files = glob.glob(onnx_pattern)

                if onnx_files:
                    onnx_path = onnx_files[0]
                    logger.info(f"Found cached ONNX model at: {onnx_path}")

                    # Configure ONNX session options to suppress ARM64 warnings
                    sess_options = ort.SessionOptions()
                    sess_options.log_severity_level = 3  # 3=ERROR (suppresses warnings)

                    # Create ONNX session with optimized settings
                    onnx_session = ort.InferenceSession(
                        onnx_path,
                        sess_options=sess_options,
                        providers=['CPUExecutionProvider']
                    )

                    use_onnx = True
                    model_mode = "ONNX Runtime (Direct Session)"
                    logger.info("✅ BGE-M3 model loaded with direct ONNX Runtime session")

                    # Log ONNX model outputs for debugging
                    logger.info("ONNX model outputs:")
                    for output in onnx_session.get_outputs():
                        logger.info(f"  - {output.name}: {output.shape}")
                else:
                    logger.warning("No cached ONNX model found, need to export first...")
                    logger.info("Attempting ONNX export via optimum...")

                    # Try to export ONNX model using optimum
                    from optimum.onnxruntime import ORTModelForFeatureExtraction

                    # This will cache the ONNX model for future use
                    temp_model = ORTModelForFeatureExtraction.from_pretrained(
                        'BAAI/bge-m3',
                        export=False,
                        provider="CPUExecutionProvider"
                    )
                    del temp_model

                    # Now find the newly exported model
                    onnx_files = glob.glob(onnx_pattern)
                    if onnx_files:
                        onnx_path = onnx_files[0]
                        logger.info(f"ONNX model exported to: {onnx_path}")

                        # Load with direct session
                        sess_options = ort.SessionOptions()
                        sess_options.log_severity_level = 3

                        onnx_session = ort.InferenceSession(
                            onnx_path,
                            sess_options=sess_options,
                            providers=['CPUExecutionProvider']
                        )

                        use_onnx = True
                        model_mode = "ONNX Runtime (Direct Session - Exported)"
                        logger.info("✅ BGE-M3 model exported and loaded with direct ONNX Runtime session")
                    else:
                        raise FileNotFoundError("ONNX export completed but model file not found")

            except Exception as onnx_error:
                logger.warning(f"ONNX Runtime setup failed: {onnx_error}")
                logger.warning(f"Error type: {type(onnx_error).__name__}")
                logger.info("Falling back to SentenceTransformers...")
                raise onnx_error
        else:
            logger.info("ONNX Runtime disabled or unavailable, using SentenceTransformers...")
            raise ImportError("ONNX disabled")

    except Exception:
        # Fallback to SentenceTransformers
        logger.info("Loading BGE-M3 with SentenceTransformers (fallback mode)...")
        model = SentenceTransformer(
            'BAAI/bge-m3',
            device='cpu',
            trust_remote_code=True
        )
        use_onnx = False
        model_mode = "SentenceTransformers (Fallback)"
        logger.info("✅ BGE-M3 model loaded with SentenceTransformers")

    logger.info(f"Model mode: {model_mode}")
    logger.info(f"PyTorch threads: {torch.get_num_threads()}")
    logger.info(f"OMP threads: {os.getenv('OMP_NUM_THREADS', 'not set')}")

    yield

    # Cleanup
    if model:
        del model
    if tokenizer:
        del tokenizer
    if onnx_session:
        del onnx_session
    torch.cuda.empty_cache() if torch.cuda.is_available() else None

app = FastAPI(
    title="BGE-M3 Embedding Service",
    description="OpenAI-compatible BGE-M3 embedding API for GT 2.0",
    version="1.0.0",
    lifespan=lifespan
)

# OpenAI-compatible request models
class EmbeddingRequest(BaseModel):
    input: List[str] = Field(..., description="Input texts to embed")
    model: str = Field(default="BAAI/bge-m3", description="Model name")
    encoding_format: str = Field(default="float", description="Encoding format")
    dimensions: Optional[int] = Field(None, description="Number of dimensions")
    user: Optional[str] = Field(None, description="User identifier")

class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int

class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int

class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """Generate embeddings using BGE-M3 model"""

    if not model and not onnx_session:
        raise HTTPException(status_code=500, detail="BGE-M3 model not loaded")

    if not request.input:
        raise HTTPException(status_code=400, detail="No input texts provided")

    start_time = time.time()

    try:
        logger.info(f"Generating embeddings for {len(request.input)} texts using {model_mode}")

        # Generate embeddings with mode-specific logic
        if use_onnx and onnx_session:
            # Direct ONNX Runtime path for maximum performance
            batch_size = min(len(request.input), 64)
            embeddings = []

            for i in range(0, len(request.input), batch_size):
                batch_texts = request.input[i:i + batch_size]

                # Tokenize
                inputs = tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    return_tensors="np",
                    max_length=512
                )

                # Run ONNX inference
                # BGE-M3 ONNX model outputs: [token_embeddings, sentence_embedding]
                outputs = onnx_session.run(
                    None,  # Get all outputs
                    {
                        'input_ids': inputs['input_ids'].astype(np.int64),
                        'attention_mask': inputs['attention_mask'].astype(np.int64)
                    }
                )

                # Get token embeddings (first output)
                token_embeddings = outputs[0]

                # Mean pooling with attention mask
                batch_embeddings = mean_pooling(token_embeddings, inputs['attention_mask'])

                # Normalize embeddings
                norms = np.linalg.norm(batch_embeddings, axis=1, keepdims=True)
                batch_embeddings = batch_embeddings / np.maximum(norms, 1e-9)

                embeddings.extend(batch_embeddings)

            embeddings = np.array(embeddings)
        else:
            # SentenceTransformers fallback path
            embeddings = model.encode(
                request.input,
                batch_size=min(len(request.input), 64),
                show_progress_bar=False,
                convert_to_tensor=False,
                normalize_embeddings=True
            )

        # Convert to list format
        if hasattr(embeddings, 'tolist'):
            embeddings = embeddings.tolist()
        elif isinstance(embeddings, list) and len(embeddings) > 0:
            if hasattr(embeddings[0], 'tolist'):
                embeddings = [emb.tolist() for emb in embeddings]

        # Create response in OpenAI format
        embedding_data = [
            EmbeddingData(
                embedding=embedding,
                index=i
            )
            for i, embedding in enumerate(embeddings)
        ]

        # Calculate token usage (rough estimation)
        total_tokens = sum(len(text.split()) for text in request.input)

        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Generated {len(embeddings)} embeddings in {processing_time_ms}ms")

        return EmbeddingResponse(
            data=embedding_data,
            model=request.model,
            usage=EmbeddingUsage(
                prompt_tokens=total_tokens,
                total_tokens=total_tokens
            )
        )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if (model or onnx_session) else "unhealthy",
        "model": "BAAI/bge-m3",
        "service": "bge-m3-embeddings",
        "mode": model_mode,
        "onnx_enabled": use_onnx,
        "pytorch_threads": torch.get_num_threads(),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)"""
    return {
        "object": "list",
        "data": [
            {
                "id": "BAAI/bge-m3",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "gt2"
            }
        ]
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "BGE-M3 Embedding Service",
        "model": "BAAI/bge-m3",
        "version": "1.0.0",
        "api": "OpenAI-compatible",
        "status": "ready" if (model or onnx_session) else "loading"
    }

if __name__ == "__main__":
    uvicorn.run(
        "embedding_server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
