# Reranker Service

Document reranking service using cross-encoder models for improved search relevance.

## Features
- Cross-encoder based reranking
- Configurable models
- Batch processing support
- RESTful API

## API Endpoints
- `POST /rerank` - Rerank documents based on query
- `GET /health` - Service health check

## Environment Variables
- `MODEL_NAME` - Reranker model to use (default: BAAI/bge-reranker-v2-m3)
- `DEVICE` - Computing device (cpu, cuda)
- `MAX_LENGTH` - Maximum sequence length

## Testing Standalone
```bash
cd services/reranker
docker-compose up

# Test with curl
curl -X POST http://localhost:8083/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "documents": ["ML is...", "Cooking is...", "AI involves..."],
    "top_k": 2
  }'
```
