# Cloud GPU Federation Bootstrap

Run AI inference services on cloud GPUs (RunPod, Lambda, Vast.ai)
and register them with the Unicorn Commander federation for automatic
request routing and cost-optimized idle shutdown.

Replaces the old `gpu_phone_home.py` + `gpu_auto_shutdown.py` pair with
a single bootstrap that speaks the federation protocol.

## Quick Start (RunPod)

1. Launch a GPU pod on RunPod
2. SSH in and run:

```bash
FEDERATION_PEERS=https://your-ops-center.example.com \
FEDERATION_KEY=your-federation-key \
SERVICE_PROFILE=music \
bash <(curl -s https://raw.githubusercontent.com/.../cloud-gpu/bootstrap.sh)
```

3. The instance registers with your federation automatically
4. Requests route to it via the federation router
5. After 5 min idle, it deregisters and shuts down to save costs

## Service Profiles

| Profile    | VRAM  | What Runs                        |
|------------|-------|----------------------------------|
| music      | 14 GB | ACE-Step 1.5 music generation    |
| image      | 12 GB | FLUX image generation            |
| llm        |  8 GB | Qwen 3.5 27B via llama.cpp       |
| embeddings |  4 GB | BGE-M3 embeddings + reranker     |
| stt        |  2 GB | WhisperX transcription           |
| tts        |  1 GB | Kokoro TTS                       |
| all        | auto  | Everything that fits (priority)  |

## GPU Tier Recommendations

| Cloud GPU    | VRAM  | Best For                            |
|--------------|-------|-------------------------------------|
| RTX 4090     | 24 GB | music OR image + stt + tts          |
| A10G         | 24 GB | image + stt + tts + embeddings      |
| A6000        | 48 GB | all services simultaneously         |
| A100 40 GB   | 40 GB | all services simultaneously         |
| A100 80 GB   | 80 GB | all + large LLMs                    |
| H100         | 80 GB | everything, fastest                 |

## Environment Variables

| Variable               | Required | Default                        | Description                           |
|------------------------|----------|--------------------------------|---------------------------------------|
| FEDERATION_PEERS       | yes      |                                | Comma-separated peer URLs             |
| FEDERATION_KEY         | yes      |                                | Shared federation secret              |
| SERVICE_PROFILE        | no       | all                            | Profile(s) to run                     |
| IDLE_TIMEOUT_MINUTES   | no       | 5                              | Minutes idle before shutdown          |
| GPU_PROVIDER           | no       | auto-detect                    | runpod, lambda, vast, generic         |
| FEDERATION_NODE_NAME   | no       | Cloud GPU {hostname}           | Display name in federation            |
| FEDERATION_REGION      | no       | cloud                          | Region tag                            |
| COMPOSE_PROJECT_DIR    | no       | /workspace/UC-Cloud-production | Path to UC-Cloud checkout             |
| RUNPOD_API_KEY         | no       |                                | For RunPod pod stop via API           |
| LAMBDA_API_KEY         | no       |                                | For Lambda instance terminate via API |

## Files

| File                         | Purpose                                         |
|------------------------------|--------------------------------------------------|
| bootstrap.sh                 | Main entrypoint: detect, start, register         |
| federation-idle-monitor.py   | Heartbeat + idle detection daemon                |
| service-profiles.yml         | Canonical service profile definitions            |

## How It Works

```
bootstrap.sh
  |
  |-- 1. Detect GPU provider (RunPod / Lambda / Vast / generic)
  |-- 2. Detect GPU hardware via nvidia-smi
  |-- 3. Select service profiles based on VRAM
  |-- 4. Start Docker services via compose
  |-- 5. Wait for health checks
  |-- 6. Register with federation peers (POST /api/v1/federation/register)
  |-- 7. Launch federation-idle-monitor.py
        |
        |-- Heartbeat every 30s (POST /api/v1/federation/heartbeat)
        |-- Check GPU utilization + service activity every 10s
        |-- After 3 consecutive idle checks past timeout:
              |-- Deregister (POST /api/v1/federation/deregister)
              |-- Stop Docker containers
              |-- Stop instance (RunPod API / Lambda API / shutdown)
```
