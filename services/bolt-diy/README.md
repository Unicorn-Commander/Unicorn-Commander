# Bolt.DIY Service

## Quick Start

### Deploy with Official Prebuilt Image (Recommended)

```bash
cd /home/muut/Production/UC-1-Pro
docker compose -f docker-compose.bolt-diy.yml up -d
```

### Build Custom Image (Optional)

If you need to customize or build from source:

```bash
cd ./services/bolt-diy

# Build the image
docker build -f Dockerfile --target bolt-ai-production -t bolt-ai:production .

# Update docker-compose.bolt-diy.yml to use custom image
# Change: image: ghcr.io/stackblitz-labs/bolt.diy:latest
# To: image: bolt-ai:production
```

## Configuration

### Environment Variables

Copy the example environment file and configure your API keys:

```bash
cp .env.example .env.local
# Edit .env.local with your API keys
```

Required environment variables are loaded from `.env.local` and passed to the container via docker-compose.

### API Keys Supported

- OpenAI (GPT-3.5, GPT-4, etc.)
- Anthropic (Claude models)
- Groq
- HuggingFace
- Google Gemini
- OpenRouter
- xAI (Grok)
- Cohere
- DeepSeek
- Mistral
- Together AI
- Azure OpenAI
- Perplexity
- Ollama (local)
- LM Studio (local)
- Custom OpenAI-compatible endpoints

## Service Details

- **Container Name**: unicorn-bolt-diy
- **Port**: 5173
- **Network**: unicorn-network (internal only)
- **External Access**: Via OAuth2-Proxy at https://bolt.localhost
- **Health Check**: HTTP GET to localhost:5173 every 30 seconds

## Volumes

1. **bolt-diy-data**: User configuration and settings
   - Mounted at: `/root/.bolt`

2. **bolt-diy-projects**: User projects
   - Mounted at: `/app/projects`

## Management Commands

### View Logs
```bash
docker logs -f unicorn-bolt-diy
```

### Restart Service
```bash
docker restart unicorn-bolt-diy
```

### Stop Service
```bash
docker compose -f ./docker-compose.bolt-diy.yml down
```

### Update to Latest Version
```bash
cd /home/muut/Production/UC-1-Pro
docker compose -f docker-compose.bolt-diy.yml pull
docker compose -f docker-compose.bolt-diy.yml up -d
```

## Troubleshooting

### Check Container Status
```bash
docker ps | grep unicorn-bolt-diy
```

### Check Health
```bash
docker inspect unicorn-bolt-diy | grep -A 10 Health
```

### Test Internal Access
```bash
curl http://localhost:5173
```

### Access Container Shell
```bash
docker exec -it unicorn-bolt-diy sh
```

## Documentation

Full deployment documentation: `./docs/BOLT-DIY-DEPLOYMENT.md`

## Official Resources

- **Repository**: https://github.com/stackblitz-labs/bolt.diy
- **Documentation**: https://stackblitz-labs.github.io/bolt.diy/
- **Docker Image**: ghcr.io/stackblitz-labs/bolt.diy
