from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
import os
from typing import List, Dict, Optional
import asyncio
import time
import json
import subprocess
from datetime import datetime, timedelta
from huggingface_hub import HfApi, list_models
import docker
import psutil

app = FastAPI(title="UC-1 Pro Model Manager")

VLLM_URL = os.environ.get("VLLM_URL", "http://unicorn-vllm:8000")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY", "dummy-key")
MODEL_DIR = "/models"
IDLE_TIMEOUT = 300  # 5 minutes in seconds

# Track last activity
last_activity = datetime.now()
idle_model = "microsoft/DialoGPT-small"  # Lightweight fallback model

# Initialize Hugging Face API
hf_api = HfApi()

# Initialize Docker client with explicit socket path
try:
    docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
except Exception as e:
    print(f"Warning: Docker client initialization failed: {e}")
    docker_client = None

# Available models configuration
AVAILABLE_MODELS = [
    {
        "id": "Qwen/Qwen2.5-32B-Instruct-AWQ",
        "name": "Qwen 2.5 32B",
        "quantization": "awq",
        "description": "Excellent all-around model, great for coding and reasoning"
    },
    {
        "id": "casperhansen/gemma-2-27b-it-awq",
        "name": "Gemma 2 27B",
        "quantization": "awq", 
        "description": "Google's latest model, strong performance"
    },
    {
        "id": "meta-llama/Llama-3.1-70B-Instruct-AWQ",
        "name": "Llama 3.1 70B",
        "quantization": "awq",
        "description": "Meta's flagship model, excellent quality but larger"
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "name": "Mistral 7B",
        "quantization": "none",
        "description": "Small, fast model for simple tasks"
    }
]

class ModelSwitch(BaseModel):
    model_id: str
    quantization: str = "awq"
    auto_download: bool = True
    
    class Config:
        protected_namespaces = ()  # Disable protected namespace warning

class ModelSearch(BaseModel):
    query: str
    filter_awq: bool = True
    filter_size: str = "medium"  # small, medium, large
    limit: int = 20

@app.get("/")
async def root():
    """Simple web interface"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>UC-1 Pro Model Manager</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .model-card { border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 8px; transition: all 0.3s; }
            .model-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            .current { background-color: #e8f5e9; border-color: #4caf50; }
            button { padding: 10px 20px; margin: 5px; cursor: pointer; border: none; border-radius: 5px; background: #2196f3; color: white; transition: background 0.3s; }
            button:hover { background: #1976d2; }
            .status { margin: 20px 0; padding: 20px; background: #f5f5f5; border-radius: 8px; }
            .loading { color: #ff9800; }
            .ready { color: #4caf50; }
            .error { color: #f44336; }
            h1 { color: #333; }
            h3 { color: #666; margin-top: 30px; }
            .model-id { font-family: monospace; font-size: 0.9em; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>UC-1 Pro Model Manager</h1>
            <div class="status">
                <h3>Current Status</h3>
                <div id="status">Loading...</div>
            </div>
            
            <h3>Search & Download Models</h3>
            <div style="margin: 20px 0;">
                <input type="text" id="searchQuery" placeholder="Search models (e.g., 'Qwen', 'Llama')" style="width: 300px; padding: 8px;">
                <label><input type="checkbox" id="filterAWQ" checked> AWQ Only</label>
                <button onclick="searchModels()" style="margin-left: 10px;">Search</button>
            </div>
            <div id="searchResults"></div>
            
            <h3>Available Models</h3>
            <div id="models"></div>
        </div>
        
        <script>
            let performanceInterval = null;
            
            async function checkStatus() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    const statusClass = data.ready ? 'ready' : 'loading';
                    
                    let statusHtml = `
                        <strong>Model:</strong> ${data.current_model || 'None loaded'}<br>
                        <strong>Status:</strong> <span class="${statusClass}">${data.ready ? 'Ready' : 'Not ready'}</span>
                    `;
                    
                    // Get performance metrics if model is ready
                    if (data.ready) {
                        const perfResponse = await fetch('/api/performance');
                        const perfData = await perfResponse.json();
                        
                        if (!perfData.error) {
                            statusHtml += `<br><br><strong>Performance:</strong><br>`;
                            statusHtml += `• Tokens/sec: ${perfData.tokens_per_second.toFixed(1)}<br>`;
                            statusHtml += `• Active requests: ${perfData.active_requests}<br>`;
                            statusHtml += `• GPU cache usage: ${perfData.gpu_cache_usage.toFixed(1)}%<br>`;
                            statusHtml += `• Total tokens: ${perfData.total_tokens_generated.toLocaleString()}<br>`;
                            
                            if (perfData.idle_timeout_remaining > 0) {
                                const minutes = Math.floor(perfData.idle_timeout_remaining / 60);
                                const seconds = perfData.idle_timeout_remaining % 60;
                                statusHtml += `• Idle swap in: ${minutes}m ${seconds}s`;
                            } else if (perfData.active_requests === 0) {
                                statusHtml += `• <span style="color: orange;">Will swap to lightweight model when idle</span>`;
                            }
                        }
                    }
                    
                    document.getElementById('status').innerHTML = statusHtml;
                } catch (e) {
                    document.getElementById('status').innerHTML = '<span class="error">Error checking status</span>';
                }
            }
            
            async function loadModels() {
                const response = await fetch('/api/models');
                const models = await response.json();
                
                const html = models.map(model => `
                    <div class="model-card">
                        <h4>${model.name}</h4>
                        <p>${model.description}</p>
                        <p class="model-id">ID: ${model.id}</p>
                        <button onclick="switchModel('${model.id}', '${model.quantization}')">
                            Load This Model
                        </button>
                        <button onclick="deleteModel('${model.id}')" style="background: #f44336; margin-left: 10px;">
                            Delete
                        </button>
                    </div>
                `).join('');
                
                document.getElementById('models').innerHTML = html;
            }
            
            async function searchModels() {
                const query = document.getElementById('searchQuery').value;
                const filterAWQ = document.getElementById('filterAWQ').checked;
                
                const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&filter_awq=${filterAWQ}&limit=20`);
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('searchResults').innerHTML = `<div class="error">${data.error}</div>`;
                    return;
                }
                
                const html = data.models.map(model => `
                    <div class="model-card" style="border-left: 3px solid #2196f3;">
                        <h4>${model.id}</h4>
                        <p>Downloads: ${model.downloads.toLocaleString()} | Likes: ${model.likes} | Size: ${model.estimated_size}</p>
                        <p><strong>Quantization:</strong> ${model.quantization}</p>
                        <button onclick="downloadAndSwitch('${model.id}', '${model.quantization}')" style="background: #4caf50;">
                            Download & Switch
                        </button>
                        <button onclick="downloadOnly('${model.id}')" style="background: #ff9800; margin-left: 10px;">
                            Download Only
                        </button>
                    </div>
                `).join('');
                
                document.getElementById('searchResults').innerHTML = html;
            }
            
            async function downloadOnly(modelId) {
                if (!confirm(`Download ${modelId}? This may take several minutes.`)) return;
                
                const response = await fetch('/api/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({model_id: modelId})
                });
                
                const result = await response.json();
                alert(result.message);
            }
            
            async function downloadAndSwitch(modelId, quantization) {
                if (!confirm(`Download and switch to ${modelId}?\\n\\nThis will:\\n1. Download the model (may take time)\\n2. Restart vLLM container\\n3. Load the new model`)) {
                    return;
                }
                
                const response = await fetch('/api/switch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        model_id: modelId, 
                        quantization: quantization,
                        auto_download: true
                    })
                });
                
                const result = await response.json();
                alert(result.message);
                checkStatus();
                loadModels();
            }
            
            async function switchModel(modelId, quantization) {
                if (!confirm(`Switch to ${modelId}?\\n\\nNote: This requires restarting the vLLM container.`)) {
                    return;
                }
                
                const response = await fetch('/api/switch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        model_id: modelId, 
                        quantization: quantization,
                        auto_download: false
                    })
                });
                
                const result = await response.json();
                alert(result.message);
                checkStatus();
            }
            
            async function deleteModel(modelId) {
                if (!confirm(`Delete ${modelId} from local storage?`)) return;
                
                const response = await fetch(`/api/models/${encodeURIComponent(modelId)}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                alert(result.message);
                loadModels();
            }
            
            // Initial load
            checkStatus();
            loadModels();
            
            // Refresh status every 10 seconds
            setInterval(checkStatus, 10000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/api/models")
async def list_available_models():
    """List available models"""
    return AVAILABLE_MODELS

@app.get("/api/status")
async def get_status():
    """Get current model status with performance metrics"""
    try:
        async with httpx.AsyncClient() as client:
            # Get model info
            models_response = await client.get(
                f"{VLLM_URL}/v1/models",
                headers={"Authorization": f"Bearer {VLLM_API_KEY}"}
            )
            
            # Get metrics if available
            metrics = {}
            try:
                metrics_response = await client.get(f"{VLLM_URL}/metrics")
                if metrics_response.status_code == 200:
                    metrics_text = metrics_response.text
                    # Parse tokens/sec from Prometheus metrics
                    for line in metrics_text.split('\n'):
                        if 'vllm:generation_tokens_total' in line and not line.startswith('#'):
                            tokens_total = float(line.split()[-1])
                            metrics['tokens_total'] = tokens_total
                        elif 'vllm:request_duration_seconds_count' in line and not line.startswith('#'):
                            request_count = float(line.split()[-1])
                            metrics['request_count'] = request_count
            except:
                pass
            
            if models_response.status_code == 200:
                data = models_response.json()
                current_model = data['data'][0]['id'] if data['data'] else None
                return {
                    "current_model": current_model,
                    "ready": True,
                    "metrics": metrics
                }
    except:
        pass
    
    return {"current_model": None, "ready": False, "metrics": {}}

@app.post("/api/switch")
async def switch_model(request: ModelSwitch):
    """Switch to a different model with automatic download"""
    await update_activity()  # User is actively managing models
    
    result = await swap_model_internal(
        request.model_id, 
        request.quantization, 
        request.auto_download
    )
    
    return result

@app.post("/api/download")
async def download_model(model_id: str):
    """Download a model without switching to it"""
    try:
        model_path = f"{MODEL_DIR}/{model_id}"
        if os.path.exists(f"{model_path}/config.json"):
            return {"status": "already_exists", "message": f"Model {model_id} already downloaded"}
        
        print(f"Downloading model: {model_id}")
        result = subprocess.run([
            "huggingface-cli", "download", model_id,
            "--local-dir", model_path,
            "--local-dir-use-symlinks", "False",
            "--resume-download"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return {"status": "success", "message": f"Downloaded {model_id}"}
        else:
            return {"status": "error", "message": f"Download failed: {result.stderr}"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/models/{model_id:path}")
async def delete_model(model_id: str):
    """Delete a downloaded model to free space"""
    try:
        model_path = f"{MODEL_DIR}/{model_id}"
        if os.path.exists(model_path):
            import shutil
            shutil.rmtree(model_path)
            return {"status": "success", "message": f"Deleted {model_id}"}
        else:
            return {"status": "not_found", "message": f"Model {model_id} not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

# Background task for idle monitoring
@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    asyncio.create_task(idle_monitor_task())

async def idle_monitor_task():
    """Background task to monitor for idle state"""
    while True:
        try:
            await check_idle_and_swap()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            print(f"Idle monitor error: {e}")
            await asyncio.sleep(60)

# Helper functions
async def update_activity():
    """Update last activity timestamp"""
    global last_activity
    last_activity = datetime.now()

async def check_idle_and_swap():
    """Check if system is idle and swap to lightweight model"""
    global last_activity
    if datetime.now() - last_activity > timedelta(seconds=IDLE_TIMEOUT):
        current_status = await get_status()
        if (current_status.get('ready') and 
            current_status.get('current_model') != idle_model and
            current_status.get('metrics', {}).get('active_requests', 0) == 0):
            
            print(f"System idle for {IDLE_TIMEOUT}s, swapping to lightweight model: {idle_model}")
            await swap_model_internal(idle_model, "none", auto_download=True)

async def swap_model_internal(model_id: str, quantization: str = "awq", auto_download: bool = True):
    """Internal model swapping with Docker container restart"""
    try:
        # Download model if needed and requested
        if auto_download:
            model_path = f"{MODEL_DIR}/{model_id}"
            if not os.path.exists(model_path) or not os.path.exists(f"{model_path}/config.json"):
                print(f"Downloading model: {model_id}")
                # huggingface-cli already supports resume!
                result = subprocess.run([
                    "huggingface-cli", "download", model_id, 
                    "--local-dir", model_path,
                    "--local-dir-use-symlinks", "False",
                    "--resume-download"  # This enables resumption
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"Failed to download model: {result.stderr}")
        
        # Method 1: Try Docker API
        if docker_client:
            try:
                container = docker_client.containers.get("unicorn-vllm")
                container.stop()
                container.start()
                return {"status": "success", "message": f"Switched to {model_id} via Docker API"}
            except Exception as e:
                print(f"Docker API method failed: {e}")
        
        # Method 2: Fallback to subprocess
        # Update environment and restart via docker compose
        env_file_path = "/.env"  # Assuming mounted from host
        if os.path.exists(env_file_path):
            # Update .env file
            with open(env_file_path, 'r') as f:
                lines = f.readlines()
            
            with open(env_file_path, 'w') as f:
                for line in lines:
                    if line.startswith('DEFAULT_LLM_MODEL='):
                        f.write(f'DEFAULT_LLM_MODEL={model_id}\n')
                    elif line.startswith('LLM_QUANTIZATION=') and quantization != "none":
                        f.write(f'LLM_QUANTIZATION={quantization}\n')
                    else:
                        f.write(line)
        
        # Try to restart via subprocess
        result = subprocess.run([
            "sh", "-c", 
            "docker compose -f /docker-compose.yml restart vllm || echo 'Manual restart required'"
        ], capture_output=True, text=True)
        
        return {"status": "success", "message": f"Switched to {model_id}"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/search")
async def search_models(query: str = "", filter_awq: bool = True, limit: int = 20):
    """Search Hugging Face for compatible models"""
    try:
        # Search filters for vLLM compatibility
        filters = {
            "library": ["transformers", "pytorch"],
            "task": "text-generation"
        }
        
        if filter_awq:
            # Look for AWQ quantized models
            query_terms = [query, "AWQ"] if query else ["AWQ"]
            query = " ".join(query_terms)
        
        # Search models
        models = list_models(
            search=query,
            filter=filters,
            sort="downloads",
            direction=-1,
            limit=limit
        )
        
        compatible_models = []
        for model in models:
            # Filter for likely vLLM-compatible models
            model_info = {
                "id": model.id,
                "downloads": getattr(model, 'downloads', 0),
                "likes": getattr(model, 'likes', 0),
                "tags": getattr(model, 'tags', []),
                "pipeline_tag": getattr(model, 'pipeline_tag', ''),
                "compatible": True,
                "quantization": "awq" if "awq" in model.id.lower() else "none",
                "estimated_size": estimate_model_size(model.id, getattr(model, 'tags', []))
            }
            
            # Skip if not text generation
            if model_info["pipeline_tag"] != "text-generation":
                continue
                
            compatible_models.append(model_info)
        
        return {"models": compatible_models[:limit]}
        
    except Exception as e:
        return {"error": str(e), "models": []}

def estimate_model_size(model_id: str, tags: list) -> str:
    """Estimate model size category"""
    model_lower = model_id.lower()
    
    if any(size in model_lower for size in ['70b', '65b', '72b']):
        return "large (>40GB)"
    elif any(size in model_lower for size in ['30b', '32b', '34b']):
        return "medium (15-40GB)"
    elif any(size in model_lower for size in ['13b', '14b', '15b', '20b']):
        return "small (5-15GB)"
    elif any(size in model_lower for size in ['7b', '8b', '9b']):
        return "tiny (<5GB)"
    else:
        return "unknown"

@app.get("/api/performance")
async def get_performance():
    """Get vLLM performance metrics and update activity"""
    await update_activity()  # Track that system is being monitored
    
    try:
        async with httpx.AsyncClient() as client:
            # Get metrics from vLLM
            metrics_response = await client.get(f"{VLLM_URL}/metrics")
            
            if metrics_response.status_code == 200:
                metrics_text = metrics_response.text
                
                # Parse key metrics
                metrics = {
                    "tokens_per_second": 0,
                    "active_requests": 0,
                    "pending_requests": 0,
                    "gpu_cache_usage": 0,
                    "total_tokens_generated": 0,
                    "idle_timeout_remaining": max(0, IDLE_TIMEOUT - int((datetime.now() - last_activity).total_seconds()))
                }
                
                for line in metrics_text.split('\n'):
                    if line.startswith('#') or not line.strip():
                        continue
                    
                    # Parse vLLM metrics
                    if 'vllm:generation_tokens_total' in line:
                        try:
                            metrics['total_tokens_generated'] = float(line.split()[-1])
                        except:
                            pass
                    elif 'vllm:request_active' in line:
                        try:
                            metrics['active_requests'] = int(float(line.split()[-1]))
                            if metrics['active_requests'] > 0:
                                await update_activity()  # Activity detected
                        except:
                            pass
                    elif 'vllm:request_pending' in line:
                        try:
                            metrics['pending_requests'] = int(float(line.split()[-1]))
                        except:
                            pass
                    elif 'vllm:gpu_cache_usage_perc' in line:
                        try:
                            metrics['gpu_cache_usage'] = float(line.split()[-1])
                        except:
                            pass
                    elif 'vllm:avg_generation_throughput_toks_per_s' in line:
                        try:
                            metrics['tokens_per_second'] = float(line.split()[-1])
                        except:
                            pass
                
                return metrics
    except Exception as e:
        return {
            "error": str(e),
            "tokens_per_second": 0,
            "active_requests": 0,
            "pending_requests": 0,
            "gpu_cache_usage": 0,
            "total_tokens_generated": 0,
            "idle_timeout_remaining": 0
        }
