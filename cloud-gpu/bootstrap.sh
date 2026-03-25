#!/bin/bash
# Federation Cloud GPU Bootstrap
# Replaces: gpu_phone_home.py + gpu_auto_shutdown.py
#
# Boots AI inference services on a cloud GPU instance and registers
# with the Unicorn Commander federation for automatic request routing.
#
# Usage:
#   FEDERATION_PEERS=https://your-ops-center.example.com \
#   FEDERATION_KEY=your-federation-key \
#   SERVICE_PROFILE=music \
#   ./bootstrap.sh
#
# Environment Variables:
#   FEDERATION_PEERS       - Comma-separated peer URLs (required)
#   FEDERATION_KEY         - Shared federation secret (required)
#   FEDERATION_NODE_NAME   - Display name (default: "Cloud GPU {hostname}")
#   FEDERATION_REGION      - Region tag (default: "cloud")
#   SERVICE_PROFILE        - Which services to run: all, music, image, stt, tts, llm, embeddings (default: all)
#   IDLE_TIMEOUT_MINUTES   - Minutes before auto-shutdown (default: 5)
#   GPU_PROVIDER           - runpod, lambda, vast (default: auto-detect)
#   COMPOSE_PROJECT_DIR    - Path to UC-Cloud-production checkout (default: /workspace/UC-Cloud-production)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/federation-bootstrap.log"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

die() {
    log "FATAL: $*"
    exit 1
}

# ---------------------------------------------------------------------------
# 1. Validate required environment
# ---------------------------------------------------------------------------

[[ -z "${FEDERATION_PEERS:-}" ]] && die "FEDERATION_PEERS is required"
[[ -z "${FEDERATION_KEY:-}" ]]   && die "FEDERATION_KEY is required"

SERVICE_PROFILE="${SERVICE_PROFILE:-all}"
IDLE_TIMEOUT_MINUTES="${IDLE_TIMEOUT_MINUTES:-5}"
FEDERATION_REGION="${FEDERATION_REGION:-cloud}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-/workspace/UC-Cloud-production}"

log "=== Federation Cloud GPU Bootstrap ==="
log "Service profile: ${SERVICE_PROFILE}"
log "Idle timeout:    ${IDLE_TIMEOUT_MINUTES} minutes"

# ---------------------------------------------------------------------------
# 2. Detect cloud provider
# ---------------------------------------------------------------------------

detect_provider() {
    if [[ -n "${RUNPOD_POD_ID:-}" ]]; then
        echo "runpod"
    elif [[ -n "${LAMBDA_INSTANCE_ID:-}" ]]; then
        echo "lambda"
    elif [[ -n "${VAST_CONTAINERLABEL:-}" ]]; then
        echo "vast"
    else
        echo "generic"
    fi
}

GPU_PROVIDER="${GPU_PROVIDER:-$(detect_provider)}"
log "Cloud provider:  ${GPU_PROVIDER}"

# ---------------------------------------------------------------------------
# 2b. Lambda persistent filesystem — pre-cached models
# ---------------------------------------------------------------------------

LAMBDA_FS_MOUNT="/lambda/nfs/persistent-storage"
MODEL_CACHE_DIR="${LAMBDA_FS_MOUNT}/models"

if [[ "${GPU_PROVIDER}" == "lambda" ]] && [[ -d "${LAMBDA_FS_MOUNT}" ]]; then
    log "Lambda persistent filesystem detected at ${LAMBDA_FS_MOUNT}"

    if [[ -d "${MODEL_CACHE_DIR}" ]]; then
        log "Pre-cached models found:"
        ls -1 "${MODEL_CACHE_DIR}/" 2>/dev/null | while read -r d; do
            size=$(du -sh "${MODEL_CACHE_DIR}/${d}" 2>/dev/null | cut -f1)
            log "  ${d}: ${size}"
        done

        # Symlink model directories so services find them
        # ACE-Step checkpoints
        if [[ -d "${MODEL_CACHE_DIR}/ACE-Step-1.5/checkpoints" ]]; then
            mkdir -p /workspace/models/ACE-Step-1.5
            ln -sfn "${MODEL_CACHE_DIR}/ACE-Step-1.5/checkpoints" /workspace/models/ACE-Step-1.5/checkpoints
            log "Linked ACE-Step checkpoints from persistent storage"
        fi

        # FLUX GGUF
        if [[ -d "${MODEL_CACHE_DIR}/flux-gguf" ]]; then
            mkdir -p /workspace/models
            ln -sfn "${MODEL_CACHE_DIR}/flux-gguf" /workspace/models/flux-gguf
            log "Linked FLUX GGUF from persistent storage"
        fi

        # HuggingFace cache (for Whisper, BGE, etc.)
        if [[ -d "${MODEL_CACHE_DIR}/huggingface" ]]; then
            export HF_HOME="${MODEL_CACHE_DIR}/huggingface"
            export TRANSFORMERS_CACHE="${MODEL_CACHE_DIR}/huggingface/hub"
            log "Set HuggingFace cache to persistent storage"
        fi
    else
        log "No pre-cached models found — services will download on first use"
        log "Upload models with: aws s3 sync ./models s3://9eb54b95-1ad1-4db4-8311-a6ae979b44da/models/ --endpoint-url https://files.us-east-3.lambda.ai"
    fi
else
    log "No persistent filesystem — models will download on first use (slower cold start)"
fi

# ---------------------------------------------------------------------------
# 3. Detect GPU hardware
# ---------------------------------------------------------------------------

detect_gpus() {
    if ! command -v nvidia-smi &>/dev/null; then
        die "nvidia-smi not found -- no NVIDIA GPU detected"
    fi

    local gpu_info
    gpu_info=$(nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader,nounits 2>/dev/null) || \
        die "nvidia-smi failed -- GPU driver issue?"

    GPU_COUNT=0
    TOTAL_VRAM_MB=0

    while IFS=',' read -r idx name mem; do
        idx=$(echo "$idx" | xargs)
        name=$(echo "$name" | xargs)
        mem=$(echo "$mem" | xargs)
        log "GPU ${idx}: ${name} (${mem} MB VRAM)"
        GPU_COUNT=$((GPU_COUNT + 1))
        TOTAL_VRAM_MB=$((TOTAL_VRAM_MB + mem))
    done <<< "$gpu_info"

    TOTAL_VRAM_GB=$((TOTAL_VRAM_MB / 1024))
    log "Total GPUs: ${GPU_COUNT}, Total VRAM: ${TOTAL_VRAM_GB} GB"
}

detect_gpus

# ---------------------------------------------------------------------------
# 4. Set node identity
# ---------------------------------------------------------------------------

HOSTNAME_SHORT="$(hostname -s 2>/dev/null || echo unknown)"

FEDERATION_NODE_ID="${FEDERATION_NODE_ID:-cloud-${GPU_PROVIDER}-${HOSTNAME_SHORT}}"
FEDERATION_NODE_NAME="${FEDERATION_NODE_NAME:-Cloud GPU ${HOSTNAME_SHORT}}"

export FEDERATION_NODE_ID FEDERATION_NODE_NAME FEDERATION_PEERS FEDERATION_KEY
export FEDERATION_REGION GPU_PROVIDER IDLE_TIMEOUT_MINUTES

log "Node ID:   ${FEDERATION_NODE_ID}"
log "Node name: ${FEDERATION_NODE_NAME}"

# ---------------------------------------------------------------------------
# 5. Resolve service profiles and determine what to start
# ---------------------------------------------------------------------------

PROFILES_YAML="${SCRIPT_DIR}/service-profiles.yml"

# Minimum VRAM (MB) required per profile
declare -A PROFILE_VRAM=(
    [embeddings]=4096
    [tts]=1024
    [stt]=2048
    [llm]=8192
    [image]=12288
    [music]=14336
)

# Priority order for the "all" profile (cheapest first)
PROFILE_PRIORITY=(embeddings stt tts llm image music)

SELECTED_PROFILES=()

select_profiles() {
    if [[ "$SERVICE_PROFILE" == "all" ]]; then
        local remaining=$TOTAL_VRAM_MB
        for p in "${PROFILE_PRIORITY[@]}"; do
            local needed=${PROFILE_VRAM[$p]}
            if (( remaining >= needed )); then
                SELECTED_PROFILES+=("$p")
                remaining=$((remaining - needed))
                log "Profile '${p}' selected (needs ${needed} MB, ${remaining} MB remaining)"
            else
                log "Profile '${p}' skipped (needs ${needed} MB, only ${remaining} MB available)"
            fi
        done
    else
        # Single or comma-separated profiles
        IFS=',' read -ra requested <<< "$SERVICE_PROFILE"
        for p in "${requested[@]}"; do
            p=$(echo "$p" | xargs)
            local needed=${PROFILE_VRAM[$p]:-0}
            if (( TOTAL_VRAM_MB >= needed )); then
                SELECTED_PROFILES+=("$p")
                log "Profile '${p}' selected"
            else
                log "WARNING: Profile '${p}' requires ${needed} MB VRAM but only ${TOTAL_VRAM_MB} MB available"
                SELECTED_PROFILES+=("$p")  # start anyway, let service handle OOM
            fi
        done
    fi

    if [[ ${#SELECTED_PROFILES[@]} -eq 0 ]]; then
        die "No service profiles could be selected for ${TOTAL_VRAM_GB} GB VRAM"
    fi

    log "Selected profiles: ${SELECTED_PROFILES[*]}"
}

select_profiles

# ---------------------------------------------------------------------------
# 6. Start services
# ---------------------------------------------------------------------------

# Map profiles to compose files and service names
declare -A PROFILE_COMPOSE_FILE=(
    [music]="services/majiks-studio-web/docker-compose.majiks.yml"
    [image]="services/artwork-studio/docker-compose.artwork.yml"
    [stt]="services/whisperx/docker-compose.yml"
    [tts]="services/kokoro-tts/docker-compose.yml"
    [llm]="docker-compose.llama-router.yml"
    [embeddings]="docker-compose.infinity.yml"
)

declare -A PROFILE_SERVICES=(
    [music]="majiks-worker"
    [image]="artwork-worker"
    [stt]="whisperx"
    [tts]="kokoro-tts"
    [llm]="llama-router"
    [embeddings]="unicorn-embeddings unicorn-reranker"
)

declare -A PROFILE_HEALTH_ENDPOINTS=(
    [music]="http://localhost:8091/health"
    [image]="http://localhost:8095/health"
    [stt]="http://localhost:9000/health"
    [tts]="http://localhost:8880/health"
    [llm]="http://localhost:8085/health"
    [embeddings]="http://localhost:8082/health"
)

STARTED_HEALTH_ENDPOINTS=()

start_services() {
    local compose_dir="${COMPOSE_PROJECT_DIR}"

    if [[ ! -d "$compose_dir" ]]; then
        log "WARNING: ${compose_dir} not found, trying ${SCRIPT_DIR}/.."
        compose_dir="${SCRIPT_DIR}/.."
    fi

    for profile in "${SELECTED_PROFILES[@]}"; do
        local compose_file="${PROFILE_COMPOSE_FILE[$profile]:-}"
        local services="${PROFILE_SERVICES[$profile]:-}"

        if [[ -z "$compose_file" ]]; then
            log "WARNING: No compose file mapped for profile '${profile}', skipping"
            continue
        fi

        local full_path="${compose_dir}/${compose_file}"
        if [[ ! -f "$full_path" ]]; then
            log "WARNING: Compose file ${full_path} not found, skipping profile '${profile}'"
            continue
        fi

        log "Starting profile '${profile}': docker compose -f ${compose_file} up -d ${services}"
        (cd "$compose_dir" && docker compose -f "$compose_file" up -d $services 2>&1 | tee -a "$LOG_FILE") || \
            log "WARNING: Failed to start profile '${profile}'"

        local health="${PROFILE_HEALTH_ENDPOINTS[$profile]:-}"
        if [[ -n "$health" ]]; then
            STARTED_HEALTH_ENDPOINTS+=("$health")
        fi
    done
}

start_services

# ---------------------------------------------------------------------------
# 7. Wait for services to be healthy
# ---------------------------------------------------------------------------

wait_for_health() {
    if [[ ${#STARTED_HEALTH_ENDPOINTS[@]} -eq 0 ]]; then
        log "No health endpoints to check"
        return 0
    fi

    log "Waiting for ${#STARTED_HEALTH_ENDPOINTS[@]} service(s) to become healthy..."
    local timeout=120
    local start_time
    start_time=$(date +%s)

    while true; do
        local all_healthy=true
        for endpoint in "${STARTED_HEALTH_ENDPOINTS[@]}"; do
            if ! curl -sf --max-time 3 "$endpoint" &>/dev/null; then
                all_healthy=false
                break
            fi
        done

        if $all_healthy; then
            log "All services healthy"
            return 0
        fi

        local elapsed=$(( $(date +%s) - start_time ))
        if (( elapsed >= timeout )); then
            log "WARNING: Timed out after ${timeout}s waiting for services to become healthy"
            log "Continuing anyway -- some services may still be loading models"
            return 0
        fi

        sleep 5
    done
}

wait_for_health

# ---------------------------------------------------------------------------
# 8. Register with federation
# ---------------------------------------------------------------------------

register_with_federation() {
    log "Registering with federation peers..."

    # Build services JSON array from started profiles
    local services_json="["
    local first=true
    for profile in "${SELECTED_PROFILES[@]}"; do
        local health="${PROFILE_HEALTH_ENDPOINTS[$profile]:-}"
        local svc_type=""
        case "$profile" in
            music)      svc_type="music_gen" ;;
            image)      svc_type="image_gen" ;;
            stt)        svc_type="stt" ;;
            tts)        svc_type="tts" ;;
            llm)        svc_type="llm" ;;
            embeddings) svc_type="embeddings" ;;
        esac

        if ! $first; then services_json+=","; fi
        first=false
        services_json+=$(cat <<ENDJSON
{"service_type":"${svc_type}","name":"${profile}","status":"running","models":[]}
ENDJSON
)
    done
    services_json+="]"

    # Build GPU info
    local gpu_json
    gpu_json=$(nvidia-smi --query-gpu=index,name,memory.total,memory.free,utilization.gpu \
        --format=csv,noheader,nounits 2>/dev/null | \
        python3 -c "
import sys, json
gpus = []
for line in sys.stdin:
    parts = [p.strip() for p in line.strip().split(',')]
    if len(parts) >= 5:
        total = int(parts[2])
        free = int(parts[3])
        gpus.append({
            'index': int(parts[0]),
            'name': parts[1],
            'memory_total_mb': total,
            'memory_free_mb': free,
            'memory_used_mb': total - free,
            'utilization_percent': int(parts[4])
        })
print(json.dumps(gpus))
" 2>/dev/null) || gpu_json="[]"

    # Build full registration payload matching federation API
    local payload
    payload=$(python3 -c "
import json, platform, os
try:
    import psutil
    cpu_cores = psutil.cpu_count(logical=True) or 0
    mem_total = round(psutil.virtual_memory().total / (1024**3), 2)
except Exception:
    cpu_cores = os.cpu_count() or 0
    mem_total = 0

payload = {
    'node_id': '${FEDERATION_NODE_ID}',
    'display_name': '${FEDERATION_NODE_NAME}',
    'endpoint_url': '',
    'auth_method': 'jwt',
    'hardware_profile': {
        'hostname': platform.node(),
        'platform': platform.platform(),
        'cpu': {
            'physical_cores': cpu_cores,
            'logical_cores': cpu_cores,
        },
        'memory': {
            'total_gb': mem_total,
        },
        'gpus': json.loads('''${gpu_json}'''),
    },
    'roles': ['inference'],
    'region': '${FEDERATION_REGION}',
    'services': json.loads('''${services_json}'''),
    'is_self': True,
}
print(json.dumps(payload))
")

    # Send registration to each peer
    IFS=',' read -ra peers <<< "$FEDERATION_PEERS"
    for peer in "${peers[@]}"; do
        peer=$(echo "$peer" | xargs)
        [[ -z "$peer" ]] && continue

        local url="${peer}/api/v1/federation/register"
        log "Registering with ${peer}..."

        local http_code
        http_code=$(curl -s -o /tmp/federation-register-response.json -w "%{http_code}" \
            -X POST "$url" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer ${FEDERATION_KEY}" \
            --max-time 20 \
            -d "$payload" 2>/dev/null) || http_code="000"

        if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
            log "Registered with ${peer} (HTTP ${http_code})"
        else
            log "WARNING: Registration with ${peer} failed (HTTP ${http_code})"
            cat /tmp/federation-register-response.json 2>/dev/null | head -3 >> "$LOG_FILE"
        fi
    done
}

register_with_federation

# ---------------------------------------------------------------------------
# 9. Start idle monitor daemon
# ---------------------------------------------------------------------------

start_idle_monitor() {
    local monitor_script="${SCRIPT_DIR}/federation-idle-monitor.py"

    if [[ ! -f "$monitor_script" ]]; then
        log "WARNING: ${monitor_script} not found, skipping idle monitor"
        return 1
    fi

    # Install httpx if not present
    pip install httpx 2>/dev/null || pip3 install httpx 2>/dev/null || \
        log "WARNING: Could not install httpx, idle monitor may fail"

    # Build health endpoints env var for the monitor
    local endpoints=""
    for ep in "${STARTED_HEALTH_ENDPOINTS[@]}"; do
        [[ -n "$endpoints" ]] && endpoints+=","
        endpoints+="$ep"
    done
    export SERVICE_HEALTH_ENDPOINTS="$endpoints"

    log "Starting federation idle monitor (timeout=${IDLE_TIMEOUT_MINUTES}m)..."
    python3 "$monitor_script" &
    local monitor_pid=$!
    log "Idle monitor started (PID ${monitor_pid})"

    # Save PID for cleanup
    echo "$monitor_pid" > /tmp/federation-idle-monitor.pid
}

start_idle_monitor

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

log ""
log "=== Bootstrap Complete ==="
log "Node:     ${FEDERATION_NODE_ID}"
log "Provider: ${GPU_PROVIDER}"
log "GPUs:     ${GPU_COUNT} (${TOTAL_VRAM_GB} GB total)"
log "Profiles: ${SELECTED_PROFILES[*]}"
log "Idle:     ${IDLE_TIMEOUT_MINUTES} minutes"
log "Log:      ${LOG_FILE}"
log ""
log "Services will auto-shutdown after ${IDLE_TIMEOUT_MINUTES} minutes of inactivity."
log "Federation peers will be notified before shutdown."
