from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import torch
import os
import json
from typing import List, Union, Optional, Dict
import logging
import numpy as np
from pathlib import Path
import asyncio
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Embeddings Service")

# Global model management
class ModelManager:
    def __init__(self):
        self.current_model_name = os.environ.get("MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")
        self.device = os.environ.get("DEVICE", "cpu")
        self.max_length = int(os.environ.get("MAX_LENGTH", "8192"))
        self.normalize = os.environ.get("NORMALIZE", "true").lower() == "true"
        self.cache_dir = os.environ.get("CACHE_DIR", "/root/.cache/huggingface")
        self.model = None
        self.available_models = {
            "nomic-ai/nomic-embed-text-v1.5": {"dimensions": 768, "max_length": 8192},
            "BAAI/bge-base-en-v1.5": {"dimensions": 768, "max_length": 512},
            "BAAI/bge-large-en-v1.5": {"dimensions": 1024, "max_length": 512},
            "BAAI/bge-small-en-v1.5": {"dimensions": 384, "max_length": 512},
            "sentence-transformers/all-MiniLM-L6-v2": {"dimensions": 384, "max_length": 256},
            "sentence-transformers/all-mpnet-base-v2": {"dimensions": 768, "max_length": 384},
            "thenlper/gte-large": {"dimensions": 1024, "max_length": 512},
            "thenlper/gte-base": {"dimensions": 768, "max_length": 512},
            "thenlper/gte-small": {"dimensions": 384, "max_length": 512},
        }
        self.load_model()
        
    def load_model(self, model_name: Optional[str] = None):
        """Load or switch to a different model"""
        if model_name:
            self.current_model_name = model_name
            
        logger.info(f"Loading embedding model: {self.current_model_name}")
        logger.info(f"Device: {self.device}, Max length: {self.max_length}, Normalize: {self.normalize}")
        
        try:
            # Configure model with trust_remote_code for nomic models
            self.model = SentenceTransformer(
                self.current_model_name,
                device=self.device,
                cache_folder=self.cache_dir,
                trust_remote_code=True  # Required for nomic models
            )
            self.model.max_seq_length = self.max_length
            
            logger.info("Model loaded successfully")
            logger.info(f"Model dimension: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
            
    def get_model_info(self):
        """Get information about the current model"""
        return {
            "name": self.current_model_name,
            "dimensions": self.model.get_sentence_embedding_dimension() if self.model else 0,
            "max_length": self.max_length,
            "device": self.device,
            "normalize": self.normalize
        }

# Initialize model manager
model_manager = ModelManager()

class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: Optional[str] = None
    encoding_format: Optional[str] = "float"
    
class ModelSwitchRequest(BaseModel):
    model_name: str
    device: Optional[str] = None
    max_length: Optional[int] = None
    normalize: Optional[bool] = None
    
class ModelSettings(BaseModel):
    device: Optional[str] = None
    max_length: Optional[int] = None
    normalize: Optional[bool] = None
    batch_size: Optional[int] = None
    cache_dir: Optional[str] = None
    
class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[dict]
    model: str
    usage: dict

@app.post("/embeddings")
@app.post("/v1/embeddings")  # OpenAI compatible endpoint
async def create_embeddings(request: EmbeddingRequest):
    """Create embeddings for the given input text(s)"""
    try:
        # Handle single string or list of strings
        if isinstance(request.input, str):
            texts = [request.input]
        else:
            texts = request.input
            
        logger.info(f"Creating embeddings for {len(texts)} text(s)")
        
        # Add task prefix for nomic models (improves performance)
        if "nomic" in model_manager.current_model_name.lower():
            texts = [f"search_document: {text}" for text in texts]
        
        # Generate embeddings
        embeddings = model_manager.model.encode(
            texts,
            convert_to_tensor=False,
            normalize_embeddings=model_manager.normalize,
            show_progress_bar=False
        )
        
        # Convert to list format
        if isinstance(embeddings, np.ndarray):
            embeddings_list = embeddings.tolist()
        else:
            embeddings_list = embeddings
        
        # Format response in OpenAI format
        data = []
        for i, embedding in enumerate(embeddings_list):
            data.append({
                "object": "embedding",
                "embedding": embedding,
                "index": i
            })
        
        # Calculate token usage (approximate)
        total_tokens = sum(len(text.split()) * 1.3 for text in texts)  # Rough estimate
        
        response = EmbeddingResponse(
            data=data,
            model=request.model or model_manager.current_model_name,
            usage={
                "prompt_tokens": int(total_tokens),
                "total_tokens": int(total_tokens)
            }
        )
        
        logger.info(f"Successfully created {len(data)} embeddings")
        return response
        
    except Exception as e:
        logger.error(f"Error creating embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model": model_manager.current_model_name,
        "dimension": model_manager.model.get_sentence_embedding_dimension(),
        "max_length": model_manager.max_length,
        "device": model_manager.device
    }

@app.get("/models")
async def list_models():
    """List available models (OpenAI compatible)"""
    return {
        "object": "list",
        "data": [
            {
                "id": model_manager.current_model_name,
                "object": "model",
                "created": 1686935002,
                "owned_by": "organization-owner"
            }
        ]
    }

@app.get("/model/info")
async def get_model_info():
    """Get detailed information about the current model"""
    return model_manager.get_model_info()

@app.get("/model/available")
async def get_available_models():
    """Get list of available models that can be loaded"""
    models = []
    for name, info in model_manager.available_models.items():
        # Check if model is cached locally
        cache_path = Path(model_manager.cache_dir) / "hub"
        model_folder = f"models--{name.replace('/', '--')}"
        is_cached = (cache_path / model_folder).exists() if cache_path.exists() else False
        
        models.append({
            "name": name,
            "dimensions": info["dimensions"],
            "max_length": info["max_length"],
            "active": name == model_manager.current_model_name,
            "cached": is_cached,
            "size": None  # Will be calculated if needed
        })
    return {"models": models}

@app.get("/model/cached")
async def get_cached_models():
    """Get list of models that are already downloaded/cached"""
    cached_models = []
    
    # Check both possible cache locations
    cache_paths = [
        Path(model_manager.cache_dir) / "hub",  # Standard HF cache location
        Path(model_manager.cache_dir)           # Alternative location
    ]
    
    for cache_path in cache_paths:
        if cache_path.exists():
            for folder in cache_path.iterdir():
                if folder.is_dir() and folder.name.startswith("models--"):
                    model_name = folder.name.replace("models--", "").replace("--", "/")
                    
                    # Skip if we already found this model
                    if any(m["name"] == model_name for m in cached_models):
                        continue
                    
                    # Get folder size
                    size = sum(f.stat().st_size for f in folder.rglob('*') if f.is_file())
                    
                    cached_models.append({
                        "name": model_name,
                        "path": str(folder),
                        "size": size,
                        "active": model_name == model_manager.current_model_name
                    })
    
    return {"cached_models": cached_models}

@app.delete("/model/cache/{model_name:path}")
async def delete_cached_model(model_name: str):
    """Delete a cached model"""
    try:
        # Don't delete the currently active model
        if model_name == model_manager.current_model_name:
            raise HTTPException(status_code=400, detail="Cannot delete the currently active model")
        
        cache_path = Path(model_manager.cache_dir) / "hub"
        model_folder = f"models--{model_name.replace('/', '--')}"
        full_path = cache_path / model_folder
        
        if full_path.exists():
            import shutil
            shutil.rmtree(full_path)
            return {"status": "success", "message": f"Deleted cached model: {model_name}"}
        else:
            raise HTTPException(status_code=404, detail="Model not found in cache")
    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/model/switch")
async def switch_model(request: ModelSwitchRequest, background_tasks: BackgroundTasks):
    """Switch to a different embedding model"""
    try:
        # Update settings if provided
        if request.device:
            model_manager.device = request.device
        if request.max_length:
            model_manager.max_length = request.max_length
        if request.normalize is not None:
            model_manager.normalize = request.normalize
            
        # Load the new model
        model_manager.load_model(request.model_name)
        
        return {
            "status": "success",
            "message": f"Switched to model: {request.model_name}",
            "model_info": model_manager.get_model_info()
        }
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/model/settings")
async def update_model_settings(settings: ModelSettings):
    """Update model settings"""
    try:
        if settings.device:
            model_manager.device = settings.device
        if settings.max_length:
            model_manager.max_length = settings.max_length
        if settings.normalize is not None:
            model_manager.normalize = settings.normalize
        if settings.cache_dir:
            model_manager.cache_dir = settings.cache_dir
            
        # Reload model with new settings
        model_manager.load_model()
        
        return {
            "status": "success",
            "message": "Settings updated",
            "settings": model_manager.get_model_info()
        }
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "service": "Embeddings",
        "version": "2.0",
        "model": model_manager.current_model_name,
        "dimension": model_manager.model.get_sentence_embedding_dimension(),
        "device": model_manager.device,
        "endpoints": {
            "/embeddings": "POST - Create embeddings (native)",
            "/v1/embeddings": "POST - Create embeddings (OpenAI compatible)",
            "/models": "GET - List available models",
            "/model/info": "GET - Get current model info",
            "/model/available": "GET - List available models",
            "/model/switch": "POST - Switch to different model",
            "/model/settings": "POST - Update model settings",
            "/health": "GET - Health check"
        }
    }