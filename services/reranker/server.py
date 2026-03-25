from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sentence_transformers import CrossEncoder
import os
import json
from typing import List, Optional, Union, Dict
import logging
import torch
from pathlib import Path
from datetime import datetime
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Reranker Service")

# Global model management
class ModelManager:
    def __init__(self):
        self.current_model_name = os.environ.get("MODEL_NAME", "mixedbread-ai/mxbai-rerank-large-v1")
        self.max_length = int(os.environ.get("MAX_LENGTH", "512"))
        self.device = os.environ.get("DEVICE", "cpu")
        self.cache_dir = os.environ.get("CACHE_DIR", "/root/.cache/huggingface")
        self.model = None
        self.available_models = {
            "mixedbread-ai/mxbai-rerank-large-v1": {"max_length": 512, "type": "cross-encoder"},
            "mixedbread-ai/mxbai-rerank-base-v1": {"max_length": 512, "type": "cross-encoder"},
            "BAAI/bge-reranker-v2-m3": {"max_length": 512, "type": "cross-encoder"},
            "BAAI/bge-reranker-large": {"max_length": 512, "type": "cross-encoder"},
            "BAAI/bge-reranker-base": {"max_length": 512, "type": "cross-encoder"},
            "cross-encoder/ms-marco-MiniLM-L-6-v2": {"max_length": 512, "type": "cross-encoder"},
            "cross-encoder/ms-marco-MiniLM-L-12-v2": {"max_length": 512, "type": "cross-encoder"},
        }
        self.load_model()
        
    def load_model(self, model_name: Optional[str] = None):
        """Load or switch to a different model"""
        if model_name:
            self.current_model_name = model_name
            
        logger.info(f"Loading reranker model: {self.current_model_name}")
        logger.info(f"Device: {self.device}, Max length: {self.max_length}")
        
        # Initialize model with trust_remote_code for compatibility
        try:
            self.model = CrossEncoder(
                self.current_model_name,
                max_length=self.max_length,
                device=self.device,
                trust_remote_code=True
            )
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load with trust_remote_code: {e}")
            # Fallback to standard loading
            self.model = CrossEncoder(
                self.current_model_name, 
                max_length=self.max_length, 
                device=self.device
            )
            logger.info("Model loaded successfully (standard mode)")
            
    def get_model_info(self):
        """Get information about the current model"""
        return {
            "name": self.current_model_name,
            "max_length": self.max_length,
            "device": self.device,
            "type": "cross-encoder"
        }

# Initialize model manager
model_manager = ModelManager()

class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_k: Optional[int] = 10
    model: Optional[str] = None
    return_documents: Optional[bool] = True
    
class ModelSwitchRequest(BaseModel):
    model_name: str
    device: Optional[str] = None
    max_length: Optional[int] = None
    
class ModelSettings(BaseModel):
    device: Optional[str] = None
    max_length: Optional[int] = None
    batch_size: Optional[int] = None
    cache_dir: Optional[str] = None

class RerankResponse(BaseModel):
    results: List[dict]
    model: str
    usage: Optional[dict] = None

@app.post("/rerank")
@app.post("/v1/rerank")  # OpenAI compatible endpoint
async def rerank(request: RerankRequest):
    """Rerank documents based on relevance to query"""
    try:
        if not request.documents:
            return RerankResponse(results=[], model=request.model or model_manager.current_model_name)
        
        logger.info(f"Reranking {len(request.documents)} documents")
        
        # Prepare pairs for scoring
        pairs = [[request.query, doc] for doc in request.documents]
        
        # Get scores with progress tracking for large batches
        if len(pairs) > 100:
            logger.info(f"Processing large batch of {len(pairs)} pairs...")
        
        scores = model_manager.model.predict(pairs, show_progress_bar=False)
        
        # Create indexed results
        indexed_results = [
            {
                "index": i,
                "score": float(score),
                "document": doc if request.return_documents else None
            }
            for i, (doc, score) in enumerate(zip(request.documents, scores))
        ]
        
        # Sort by score (descending)
        indexed_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Get top_k results
        top_results = indexed_results[:request.top_k] if request.top_k else indexed_results
        
        # Clean up results (remove None documents if not returning)
        if not request.return_documents:
            for result in top_results:
                result.pop('document', None)
        
        logger.info(f"Reranking complete. Top score: {top_results[0]['score'] if top_results else 0}")
        
        # Estimate token usage
        total_tokens = sum(len(doc.split()) + len(request.query.split()) for doc in request.documents) * 1.3
        
        return RerankResponse(
            results=top_results,
            model=request.model or model_manager.current_model_name,
            usage={
                "prompt_tokens": int(total_tokens),
                "total_tokens": int(total_tokens)
            }
        )
        
    except Exception as e:
        logger.error(f"Error in reranking: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model": model_manager.current_model_name,
        "device": model_manager.device,
        "max_length": model_manager.max_length
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
            "max_length": info["max_length"],
            "type": info["type"],
            "active": name == model_manager.current_model_name,
            "cached": is_cached
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
            shutil.rmtree(full_path)
            return {"status": "success", "message": f"Deleted cached model: {model_name}"}
        else:
            raise HTTPException(status_code=404, detail="Model not found in cache")
    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/model/switch")
async def switch_model(request: ModelSwitchRequest, background_tasks: BackgroundTasks):
    """Switch to a different reranker model"""
    try:
        # Update settings if provided
        if request.device:
            model_manager.device = request.device
        if request.max_length:
            model_manager.max_length = request.max_length
            
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
        "service": "Reranker",
        "version": "2.0",
        "model": model_manager.current_model_name,
        "device": model_manager.device,
        "endpoints": {
            "/rerank": "POST - Rerank documents (native)",
            "/v1/rerank": "POST - Rerank documents (OpenAI compatible)",
            "/models": "GET - List available models",
            "/model/info": "GET - Get current model info",
            "/model/available": "GET - List available models",
            "/model/switch": "POST - Switch to different model",
            "/model/settings": "POST - Update model settings",
            "/health": "GET - Health check"
        }
    }
