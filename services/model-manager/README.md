# Model Manager Service

Web UI for managing vLLM models in UC-1 Pro.

## Features
- View currently loaded model
- Switch between pre-configured models
- Simple web interface

## API Endpoints
- `GET /` - Web UI
- `GET /api/models` - List available models
- `GET /api/status` - Current model status
- `POST /api/switch` - Switch model (returns instructions)
- `GET /health` - Health check

## Testing Standalone
```bash
cd services/model-manager
docker-compose up
# Visit http://localhost:8084
```

## Environment Variables
- `VLLM_URL` - vLLM API endpoint
- `VLLM_API_KEY` - API key for vLLM
