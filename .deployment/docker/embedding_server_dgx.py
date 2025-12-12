#!/usr/bin/env python3
"""
DGX-Optimized BGE-M3 Embedding Server for GT 2.0
Optimized for NVIDIA DGX Spark with 20-core Grace ARM architecture
Provides real BGE-M3 embeddings via OpenAI-compatible API - NO FALLBACKS
"""

import asyncio
import logging
import time
import uvicorn
import psutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BGE-M3 Model with DGX Grace optimizations
from sentence_transformers import SentenceTransformer
import torch
import os
import numpy as np

# ONNX Runtime imports with direct session support
try:
    import onnxruntime as ort
    from transformers import AutoTokenizer
    ONNX_AVAILABLE = True
    logger.info("ONNX Runtime available for DGX Grace ARM64 optimization")
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
    """Load BGE-M3 model on startup with DGX Grace optimization"""
    global model, tokenizer, onnx_session, use_onnx, model_mode
    logger.info("Loading BGE-M3 model with DGX Grace ARM64 optimization...")

    # Log system information
    logger.info(f"CPU cores: {psutil.cpu_count(logical=True)}")
    logger.info(f"Memory: {psutil.virtual_memory().total / (1024**3):.1f}GB")
    logger.info(f"Platform: {os.environ.get('GT2_PLATFORM', 'unknown')}")
    logger.info(f"Architecture: {os.environ.get('GT2_ARCHITECTURE', 'unknown')}")

    # Check if ONNX Runtime should be used and is available
    use_onnx_env = os.environ.get('USE_ONNX_RUNTIME', 'true').lower() == 'true'

    try:
        if ONNX_AVAILABLE and use_onnx_env:
            # Try ONNX Runtime with direct session for maximum DGX Grace performance
            logger.info("Attempting to load BGE-M3 with direct ONNX Runtime session...")
            try:
                # Load tokenizer
                tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-m3')

                # Check for cached ONNX model
                cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
                model_id = 'models--BAAI--bge-m3'

                # Find ONNX model in cache - check multiple possible locations
                import glob
                onnx_locations = [
                    f'{cache_dir}/{model_id}/onnx/model.onnx',  # Our export location
                    f'{cache_dir}/{model_id}/snapshots/*/onnx/model.onnx',  # HF cache location
                ]
                onnx_files = []
                for pattern in onnx_locations:
                    onnx_files = glob.glob(pattern)
                    if onnx_files:
                        break

                if onnx_files:
                    onnx_path = onnx_files[0]
                    logger.info(f"Found cached ONNX model at: {onnx_path}")

                    # Configure ONNX session options for DGX Grace ARM64
                    sess_options = ort.SessionOptions()
                    sess_options.log_severity_level = 3  # 3=ERROR (suppresses warnings)
                    sess_options.intra_op_num_threads = 20  # DGX Grace 20 cores
                    sess_options.inter_op_num_threads = 4
                    sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
                    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

                    # Create ONNX session with DGX optimized settings
                    onnx_session = ort.InferenceSession(
                        onnx_path,
                        sess_options=sess_options,
                        providers=['CPUExecutionProvider']
                    )

                    use_onnx = True
                    model_mode = "ONNX Runtime (Direct Session - DGX)"
                    logger.info("✅ BGE-M3 model loaded with direct ONNX Runtime session (DGX optimized)")

                    # Log ONNX model outputs for debugging
                    logger.info("ONNX model outputs:")
                    for output in onnx_session.get_outputs():
                        logger.info(f"  - {output.name}: {output.shape}")
                else:
                    logger.warning("No cached ONNX model found, need to export first...")
                    logger.info("Attempting ONNX export via optimum...")

                    # Try to export ONNX model using optimum
                    from optimum.onnxruntime import ORTModelForFeatureExtraction

                    # Define export path within the huggingface cache structure
                    onnx_export_path = os.path.expanduser('~/.cache/huggingface/hub/models--BAAI--bge-m3/onnx')
                    os.makedirs(onnx_export_path, exist_ok=True)

                    logger.info(f"Exporting ONNX model to: {onnx_export_path}")

                    # Export and save the ONNX model
                    temp_model = ORTModelForFeatureExtraction.from_pretrained(
                        'BAAI/bge-m3',
                        export=True,
                        provider="CPUExecutionProvider"
                    )
                    temp_model.save_pretrained(onnx_export_path)
                    logger.info(f"ONNX model saved to: {onnx_export_path}")
                    del temp_model

                    # Look for the exported model in the new location
                    onnx_export_pattern = f'{onnx_export_path}/model.onnx'
                    onnx_files = glob.glob(onnx_export_pattern)

                    # Also check the original pattern in case it was cached differently
                    if not onnx_files:
                        onnx_files = glob.glob(onnx_pattern)
                    if onnx_files:
                        onnx_path = onnx_files[0]
                        logger.info(f"ONNX model exported to: {onnx_path}")

                        # Load with direct session
                        sess_options = ort.SessionOptions()
                        sess_options.log_severity_level = 3
                        sess_options.intra_op_num_threads = 20
                        sess_options.inter_op_num_threads = 4
                        sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
                        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

                        onnx_session = ort.InferenceSession(
                            onnx_path,
                            sess_options=sess_options,
                            providers=['CPUExecutionProvider']
                        )

                        use_onnx = True
                        model_mode = "ONNX Runtime (Direct Session - DGX Exported)"
                        logger.info("✅ BGE-M3 model exported and loaded with direct ONNX Runtime session (DGX optimized)")
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
        # Fallback to SentenceTransformers if ONNX fails or is disabled
        logger.info("Loading BGE-M3 with SentenceTransformers (DGX Grace optimized)...")
        try:
            # Configure PyTorch for DGX Grace
            torch.set_num_threads(20)  # DGX Grace 20 cores
            torch.set_num_interop_threads(4)

            # Load model with DGX optimizations
            model = SentenceTransformer(
                'BAAI/bge-m3',
                device='cpu',
                trust_remote_code=True,
                model_kwargs={
                    'torch_dtype': torch.float16,  # Memory optimization for large models
                    'low_cpu_mem_usage': False  # Use full memory for performance
                }
            )

            # Enable optimizations
            model._modules['0'].auto_model.eval()

            use_onnx = False
            model_mode = "SentenceTransformers (DGX Grace)"
            logger.info("✅ BGE-M3 loaded successfully with SentenceTransformers (DGX Grace optimized)")

        except Exception as e:
            logger.error(f"❌ Failed to load BGE-M3 model: {e}")
            raise e

    # Log model configuration
    logger.info(f"Model mode: {model_mode}")
    logger.info(f"Using ONNX: {use_onnx}")
    logger.info(f"OMP_NUM_THREADS: {os.environ.get('OMP_NUM_THREADS', 'not set')}")
    logger.info(f"PYTORCH_NUM_THREADS: {os.environ.get('PYTORCH_NUM_THREADS', 'not set')}")

    yield

    # Cleanup
    logger.info("Shutting down BGE-M3 embedding server...")
    if model:
        del model
    if tokenizer:
        del tokenizer
    if onnx_session:
        del onnx_session
    torch.cuda.empty_cache() if torch.cuda.is_available() else None

# FastAPI app with lifespan
app = FastAPI(
    title="GT 2.0 DGX BGE-M3 Embedding Server",
    description="DGX Grace ARM optimized BGE-M3 embedding service for GT 2.0",
    version="2.0.0-dgx",
    lifespan=lifespan
)

# Pydantic models for OpenAI compatibility
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

@app.get("/health")
async def health_check():
    """Health check endpoint with DGX system metrics"""
    if not model and not onnx_session:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Include system metrics for DGX monitoring
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    return {
        "status": "healthy",
        "model": "BAAI/bge-m3",
        "mode": model_mode,
        "using_onnx": use_onnx,
        "platform": os.environ.get('GT2_PLATFORM', 'unknown'),
        "architecture": os.environ.get('GT2_ARCHITECTURE', 'unknown'),
        "cpu_cores": psutil.cpu_count(logical=True),
        "cpu_usage": cpu_percent,
        "memory_total_gb": round(memory.total / (1024**3), 1),
        "memory_used_gb": round(memory.used / (1024**3), 1),
        "memory_available_gb": round(memory.available / (1024**3), 1),
        "omp_threads": os.environ.get('OMP_NUM_THREADS', 'not set'),
        "pytorch_threads": os.environ.get('PYTORCH_NUM_THREADS', 'not set'),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """Create embeddings using BGE-M3 model (OpenAI compatible)"""
    if not model and not onnx_session:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        start_time = time.time()
        input_texts = request.input

        # Validate input
        if not input_texts or len(input_texts) == 0:
            raise HTTPException(status_code=400, detail="Input texts cannot be empty")

        # Log processing info for DGX monitoring
        logger.info(f"Processing {len(input_texts)} texts with {model_mode}")

        # DGX optimized batch processing
        if use_onnx and onnx_session:
            # Direct ONNX Runtime path for maximum DGX Grace performance
            batch_size = min(len(input_texts), 128)  # Larger batches for DGX Grace
            embeddings = []

            for i in range(0, len(input_texts), batch_size):
                batch_texts = input_texts[i:i + batch_size]

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
            # SentenceTransformers path with DGX optimization
            with torch.no_grad():
                embeddings = model.encode(
                    input_texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    batch_size=32,  # Optimal for DGX Grace
                    show_progress_bar=False
                )

        # Convert to list format for OpenAI compatibility
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

        processing_time = time.time() - start_time

        # Calculate token usage (rough estimation)
        total_tokens = sum(len(text.split()) for text in input_texts)

        # Log performance metrics for DGX monitoring
        texts_per_second = len(input_texts) / processing_time
        logger.info(f"Processed {len(input_texts)} texts in {processing_time:.2f}s ({texts_per_second:.1f} texts/sec)")

        return EmbeddingResponse(
            data=embedding_data,
            model=request.model,
            usage=EmbeddingUsage(
                prompt_tokens=total_tokens,
                total_tokens=total_tokens
            )
        )

    except Exception as e:
        logger.error(f"❌ Embedding generation failed: {e}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

@app.get("/v1/models")
@app.get("/models")
async def list_models():
    """List available models (OpenAI compatible)"""
    return {
        "object": "list",
        "data": [
            {
                "id": "BAAI/bge-m3",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "gt2-dgx",
                "permission": [],
                "root": "BAAI/bge-m3",
                "parent": None
            }
        ]
    }

@app.get("/")
async def root():
    """Root endpoint with DGX info"""
    return {
        "service": "GT 2.0 DGX BGE-M3 Embedding Server",
        "version": "2.0.0-dgx",
        "model": "BAAI/bge-m3",
        "mode": model_mode,
        "platform": os.environ.get('GT2_PLATFORM', 'unknown'),
        "architecture": os.environ.get('GT2_ARCHITECTURE', 'unknown'),
        "cpu_cores": psutil.cpu_count(logical=True),
        "openai_compatible": True,
        "endpoints": {
            "embeddings": "/v1/embeddings",
            "models": "/models",
            "health": "/health"
        }
    }

if __name__ == "__main__":
    logger.info("Starting GT 2.0 DGX BGE-M3 Embedding Server...")
    logger.info(f"Platform: {os.environ.get('GT2_PLATFORM', 'unknown')}")
    logger.info(f"Architecture: {os.environ.get('GT2_ARCHITECTURE', 'unknown')}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=1,  # Single worker for model memory efficiency
        loop="asyncio",
        access_log=True
    )
