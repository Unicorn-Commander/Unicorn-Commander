#!/usr/bin/env python3
"""
Infinity Idle Proxy
Starts Infinity containers on-demand and stops them after idle timeout.
"""

import asyncio
import time
import logging
import os
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

# Configuration
IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", "1800"))  # 30 min default
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))  # 1 min
CONTAINER_START_TIMEOUT = int(os.getenv("CONTAINER_START_TIMEOUT", "120"))  # 2 min for model loading

SERVICES = {
    "embeddings": {
        "container": "unicorn-embeddings",
        "upstream": "http://unicorn-embeddings:7997",
        "port": 8082,
    },
    "reranker": {
        "container": "unicorn-reranker",
        "upstream": "http://unicorn-reranker:7997",
        "port": 8083,
    }
}

# State
last_activity = {"embeddings": 0, "reranker": 0}
container_status = {"embeddings": "unknown", "reranker": "unknown"}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def run_docker_command(cmd: list[str]) -> tuple[int, str]:
    """Run a docker command asynchronously."""
    proc = await asyncio.create_subprocess_exec(
        "docker", *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode() + stderr.decode()


async def is_container_running(container: str) -> bool:
    """Check if a container is running."""
    code, output = await run_docker_command(["inspect", "-f", "{{.State.Running}}", container])
    return code == 0 and "true" in output.lower()


async def start_container(container: str) -> bool:
    """Start a container and wait for it to be healthy."""
    logger.info(f"Starting container: {container}")
    code, output = await run_docker_command(["start", container])
    if code != 0:
        logger.error(f"Failed to start {container}: {output}")
        return False

    # Wait for container to be healthy
    start_time = time.time()
    while time.time() - start_time < CONTAINER_START_TIMEOUT:
        code, output = await run_docker_command(["inspect", "-f", "{{.State.Health.Status}}", container])
        if "healthy" in output.lower():
            logger.info(f"Container {container} is healthy")
            return True
        await asyncio.sleep(2)

    logger.warning(f"Container {container} started but health check timed out")
    return True  # Container started, might just be loading model


async def stop_container(container: str) -> bool:
    """Stop a container."""
    logger.info(f"Stopping container: {container}")
    code, output = await run_docker_command(["stop", container])
    if code != 0:
        logger.error(f"Failed to stop {container}: {output}")
        return False
    return True


async def ensure_running(service: str) -> bool:
    """Ensure a service container is running."""
    config = SERVICES[service]
    container = config["container"]

    if await is_container_running(container):
        container_status[service] = "running"
        return True

    container_status[service] = "starting"
    success = await start_container(container)
    container_status[service] = "running" if success else "error"
    return success


async def idle_checker():
    """Background task to stop idle containers."""
    logger.info(f"Idle checker started (timeout: {IDLE_TIMEOUT_SECONDS}s)")
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        current_time = time.time()

        for service, config in SERVICES.items():
            last = last_activity[service]
            if last > 0 and (current_time - last) > IDLE_TIMEOUT_SECONDS:
                if await is_container_running(config["container"]):
                    logger.info(f"Stopping idle service: {service} (idle for {int(current_time - last)}s)")
                    await stop_container(config["container"])
                    container_status[service] = "stopped"
                    last_activity[service] = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Start idle checker
    task = asyncio.create_task(idle_checker())
    logger.info("Infinity Idle Proxy started")
    yield
    task.cancel()


app = FastAPI(title="Infinity Idle Proxy", lifespan=lifespan)


@app.get("/health")
async def health():
    """Proxy health check."""
    return {
        "status": "healthy",
        "idle_timeout_seconds": IDLE_TIMEOUT_SECONDS,
        "services": container_status,
        "last_activity": {k: int(time.time() - v) if v > 0 else None for k, v in last_activity.items()}
    }


@app.get("/status")
async def status():
    """Detailed status of services."""
    result = {}
    for service, config in SERVICES.items():
        running = await is_container_running(config["container"])
        result[service] = {
            "container": config["container"],
            "running": running,
            "last_activity_seconds_ago": int(time.time() - last_activity[service]) if last_activity[service] > 0 else None,
            "upstream": config["upstream"]
        }
    return result


# Manual start/stop endpoints
@app.post("/embeddings/start")
async def start_embeddings():
    """Manually start the embeddings container."""
    service = "embeddings"
    config = SERVICES[service]
    container = config["container"]

    if await is_container_running(container):
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} is already running",
            "service": service
        })

    container_status[service] = "starting"
    success = await start_container(container)

    if success:
        container_status[service] = "running"
        last_activity[service] = time.time()
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} started successfully",
            "service": service
        })
    else:
        container_status[service] = "error"
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": f"Failed to start container {container}",
            "service": service
        })


@app.post("/embeddings/stop")
async def stop_embeddings():
    """Manually stop the embeddings container."""
    service = "embeddings"
    config = SERVICES[service]
    container = config["container"]

    if not await is_container_running(container):
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} is already stopped",
            "service": service
        })

    success = await stop_container(container)

    if success:
        container_status[service] = "stopped"
        last_activity[service] = 0
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} stopped successfully",
            "service": service
        })
    else:
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": f"Failed to stop container {container}",
            "service": service
        })


@app.post("/reranker/start")
async def start_reranker():
    """Manually start the reranker container."""
    service = "reranker"
    config = SERVICES[service]
    container = config["container"]

    if await is_container_running(container):
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} is already running",
            "service": service
        })

    container_status[service] = "starting"
    success = await start_container(container)

    if success:
        container_status[service] = "running"
        last_activity[service] = time.time()
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} started successfully",
            "service": service
        })
    else:
        container_status[service] = "error"
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": f"Failed to start container {container}",
            "service": service
        })


@app.post("/reranker/stop")
async def stop_reranker():
    """Manually stop the reranker container."""
    service = "reranker"
    config = SERVICES[service]
    container = config["container"]

    if not await is_container_running(container):
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} is already stopped",
            "service": service
        })

    success = await stop_container(container)

    if success:
        container_status[service] = "stopped"
        last_activity[service] = 0
        return JSONResponse(content={
            "success": True,
            "message": f"Container {container} stopped successfully",
            "service": service
        })
    else:
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": f"Failed to stop container {container}",
            "service": service
        })


@app.api_route("/v1/embeddings", methods=["POST"])
@app.api_route("/embeddings", methods=["POST"])
async def proxy_embeddings(request: Request):
    """Proxy embeddings requests to Infinity."""
    return await proxy_request("embeddings", request, "/embeddings")


@app.api_route("/v1/rerank", methods=["POST"])
@app.api_route("/rerank", methods=["POST"])
async def proxy_rerank(request: Request):
    """Proxy rerank requests to Infinity."""
    return await proxy_request("reranker", request, "/rerank")


@app.get("/models")
@app.get("/v1/models")
async def proxy_models(request: Request):
    """Proxy models endpoint - combines both services."""
    models = []
    for service in SERVICES:
        if await is_container_running(SERVICES[service]["container"]):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{SERVICES[service]['upstream']}/models")
                    if resp.status_code == 200:
                        data = resp.json()
                        if "data" in data:
                            models.extend(data["data"])
            except Exception:
                pass
    return {"object": "list", "data": models}


async def proxy_request(service: str, request: Request, path: str) -> Response:
    """Generic request proxying with container management."""
    config = SERVICES[service]

    # Ensure container is running
    if not await ensure_running(service):
        return JSONResponse(
            status_code=503,
            content={"error": f"Failed to start {service} service"}
        )

    # Update activity timestamp
    last_activity[service] = time.time()

    # Forward request
    try:
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.request(
                method=request.method,
                url=f"{config['upstream']}{path}",
                content=body,
                headers=headers
            )

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"error": "Upstream timeout"})
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return JSONResponse(status_code=502, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
