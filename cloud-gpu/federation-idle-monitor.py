#!/usr/bin/env python3
"""
Federation Idle Monitor for Cloud GPU Instances

Combines heartbeat (phone-home) and idle detection (auto-shutdown) into one
daemon. Replaces the old gpu_phone_home.py + gpu_auto_shutdown.py pair.

Flow:
  1. Send heartbeat to federation peers every 30 seconds
  2. Track local GPU utilization and service activity
  3. After IDLE_TIMEOUT_MINUTES of no activity, initiate shutdown:
     a. Deregister from federation peers
     b. Stop local Docker services gracefully
     c. Stop the cloud instance (RunPod API / Lambda API / system shutdown)

Environment Variables:
  FEDERATION_PEERS              - Comma-separated peer URLs (required)
  FEDERATION_KEY                - Shared federation secret (required)
  FEDERATION_NODE_ID            - Unique node identifier
  IDLE_TIMEOUT_MINUTES          - Minutes idle before shutdown (default: 5)
  FEDERATION_HEARTBEAT_INTERVAL - Seconds between heartbeats (default: 30)
  GPU_PROVIDER                  - runpod, lambda, vast, generic (default: auto-detect)
  SERVICE_HEALTH_ENDPOINTS      - Comma-separated health URLs to check for activity
  RUNPOD_POD_ID                 - RunPod pod ID (auto-detected)
  RUNPOD_API_KEY                - RunPod API key for pod stop
  LAMBDA_INSTANCE_ID            - Lambda instance ID (auto-detected)
  LAMBDA_API_KEY                - Lambda API key for instance terminate
"""

import json
import logging
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime

try:
    import httpx
except ImportError:
    print("httpx not installed. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/federation-idle-monitor.log", mode="a"),
    ],
)
logger = logging.getLogger("federation-idle-monitor")


class FederationIdleMonitor:
    """Combined heartbeat + idle-shutdown daemon for cloud GPU instances."""

    def __init__(self):
        # Federation config
        self.peers = [
            p.strip()
            for p in os.getenv("FEDERATION_PEERS", "").split(",")
            if p.strip()
        ]
        self.key = os.getenv("FEDERATION_KEY", "")
        self.node_id = os.getenv(
            "FEDERATION_NODE_ID",
            f"cloud-{os.getenv('HOSTNAME', 'unknown')}",
        )

        # Timing
        self.idle_timeout = int(os.getenv("IDLE_TIMEOUT_MINUTES", "5")) * 60
        self.heartbeat_interval = int(
            os.getenv("FEDERATION_HEARTBEAT_INTERVAL", "30")
        )

        # Provider
        self.gpu_provider = os.getenv("GPU_PROVIDER", self._detect_provider())

        # Activity tracking
        self.last_activity = time.time()  # assume active at start
        self.consecutive_idle_checks = 0
        self.required_idle_checks = 3  # safety: 3 consecutive checks required
        self.activity_check_interval = 10  # seconds between checks

        # Service health endpoints populated by bootstrap
        endpoints_str = os.getenv("SERVICE_HEALTH_ENDPOINTS", "")
        self.service_endpoints = [
            e.strip() for e in endpoints_str.split(",") if e.strip()
        ]

        # State
        self.running = True
        self.client = httpx.Client(timeout=15.0)

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    # ------------------------------------------------------------------
    # Provider detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_provider() -> str:
        if os.getenv("RUNPOD_POD_ID"):
            return "runpod"
        if os.getenv("LAMBDA_INSTANCE_ID"):
            return "lambda"
        if os.getenv("VAST_CONTAINERLABEL"):
            return "vast"
        return "generic"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        """Main loop: heartbeat + idle check every N seconds."""
        logger.info(
            "Starting federation idle monitor: node=%s provider=%s "
            "idle_timeout=%ds heartbeat=%ds endpoints=%d",
            self.node_id,
            self.gpu_provider,
            self.idle_timeout,
            self.heartbeat_interval,
            len(self.service_endpoints),
        )

        last_heartbeat = 0.0

        while self.running:
            now = time.time()

            # --- heartbeat ---
            if now - last_heartbeat >= self.heartbeat_interval:
                self._send_heartbeat()
                last_heartbeat = now

            # --- activity check ---
            if self._check_activity():
                self.last_activity = now
                self.consecutive_idle_checks = 0
            else:
                idle_secs = now - self.last_activity
                if idle_secs >= self.idle_timeout:
                    self.consecutive_idle_checks += 1
                    logger.warning(
                        "Idle check %d/%d (idle for %ds)",
                        self.consecutive_idle_checks,
                        self.required_idle_checks,
                        int(idle_secs),
                    )
                    if self.consecutive_idle_checks >= self.required_idle_checks:
                        logger.info("Idle threshold reached. Initiating shutdown.")
                        self._shutdown_sequence()
                        return

            time.sleep(self.activity_check_interval)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _send_heartbeat(self):
        """Send heartbeat to all federation peers."""
        payload = self._build_heartbeat()
        for peer in self.peers:
            url = f"{peer}/api/v1/federation/heartbeat"
            try:
                resp = self.client.post(
                    url,
                    json=payload,
                    headers=self._auth_headers(),
                )
                if resp.status_code == 200:
                    logger.debug("Heartbeat OK: %s", peer)
                else:
                    logger.warning("Heartbeat %s returned %d", peer, resp.status_code)
            except Exception as exc:
                logger.warning("Heartbeat to %s failed: %s", peer, exc)

    def _build_heartbeat(self) -> dict:
        """Build heartbeat payload matching federation API schema."""
        payload: dict = {
            "node_id": self.node_id,
            "load": {},
            "services": [],
        }

        # GPU metrics
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                gpus = []
                for line in result.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        total = int(parts[2])
                        free = int(parts[3])
                        gpus.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_total_mb": total,
                            "memory_free_mb": free,
                            "memory_used_mb": total - free,
                            "utilization_percent": int(parts[4]),
                        })
                payload["hardware_profile"] = {"gpus": gpus}
        except Exception:
            pass

        # CPU load
        try:
            load1, load5, load15 = os.getloadavg()
            payload["load"] = {
                "cpu_percent": load1,
                "load_avg_1m": load1,
                "load_avg_5m": load5,
            }
        except Exception:
            pass

        # Service status
        for endpoint in self.service_endpoints:
            try:
                resp = self.client.get(endpoint, timeout=3.0)
                status = "running" if resp.status_code == 200 else "unhealthy"
            except Exception:
                status = "unreachable"
            # Derive service type from endpoint port
            payload["services"].append({"endpoint": endpoint, "status": status})

        return payload

    # ------------------------------------------------------------------
    # Activity detection
    # ------------------------------------------------------------------

    def _check_activity(self) -> bool:
        """Return True if any GPU or service is actively doing work."""
        # Check GPU utilization
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    util = int(line.strip())
                    if util > 10:  # meaningful GPU work
                        return True
        except Exception:
            pass

        # Check service health endpoints for active_requests
        for endpoint in self.service_endpoints:
            try:
                resp = self.client.get(endpoint, timeout=3.0)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        if isinstance(data, dict):
                            # Various services report activity differently
                            if data.get("active_requests", 0) > 0:
                                return True
                            if data.get("busy", False):
                                return True
                            if data.get("processing", 0) > 0:
                                return True
                    except Exception:
                        pass
            except Exception:
                pass

        return False

    # ------------------------------------------------------------------
    # Shutdown sequence
    # ------------------------------------------------------------------

    def _shutdown_sequence(self):
        """Graceful shutdown: deregister -> stop services -> stop instance."""
        logger.info("=== SHUTDOWN SEQUENCE STARTED ===")

        # 1. Deregister from federation
        self._deregister()

        # 2. Stop Docker services
        self._stop_services()

        # 3. Stop cloud instance
        self._stop_instance()

    def _deregister(self):
        """Notify federation peers that this node is going offline."""
        for peer in self.peers:
            try:
                url = f"{peer}/api/v1/federation/deregister"
                resp = self.client.post(
                    url,
                    json={"node_id": self.node_id},
                    headers=self._auth_headers(),
                )
                logger.info("Deregistered from %s (HTTP %d)", peer, resp.status_code)
            except Exception as exc:
                logger.warning("Deregister from %s failed: %s", peer, exc)

    def _stop_services(self):
        """Stop known Docker containers gracefully."""
        containers = [
            "majiks-worker",
            "artwork-worker",
            "whisperx",
            "kokoro-tts",
            "llama-router",
            "unicorn-embeddings",
            "unicorn-reranker",
        ]
        for name in containers:
            try:
                result = subprocess.run(
                    ["docker", "stop", "-t", "15", name],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    logger.info("Stopped container: %s", name)
            except subprocess.TimeoutExpired:
                logger.warning("Timeout stopping %s, killing", name)
                subprocess.run(
                    ["docker", "kill", name],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass  # container may not exist

    def _stop_instance(self):
        """Stop the cloud instance via provider API or system shutdown."""
        if self.gpu_provider == "runpod":
            self._shutdown_runpod()
        elif self.gpu_provider == "lambda":
            self._shutdown_lambda()
        elif self.gpu_provider == "vast":
            self._shutdown_vast()
        else:
            self._shutdown_generic()

    def _shutdown_runpod(self):
        """Stop a RunPod pod via GraphQL API."""
        pod_id = os.getenv("RUNPOD_POD_ID")
        api_key = os.getenv("RUNPOD_API_KEY")
        if not pod_id or not api_key:
            logger.warning("RUNPOD_POD_ID or RUNPOD_API_KEY missing, falling back to system shutdown")
            self._shutdown_generic()
            return

        mutation = """
        mutation stopPod($input: PodStopInput!) {
            podStop(input: $input) {
                id
                desiredStatus
            }
        }
        """
        try:
            resp = self.client.post(
                "https://api.runpod.io/graphql",
                json={
                    "query": mutation,
                    "variables": {"input": {"podId": pod_id}},
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            data = resp.json()
            if "errors" in data:
                logger.error("RunPod API error: %s", data["errors"])
                self._shutdown_generic()
            else:
                logger.info("RunPod pod %s stop initiated: %s", pod_id, data.get("data"))
        except Exception as exc:
            logger.error("RunPod stop failed: %s", exc)
            self._shutdown_generic()

    def _shutdown_lambda(self):
        """Terminate a Lambda Labs instance via API."""
        instance_id = os.getenv("LAMBDA_INSTANCE_ID")
        api_key = os.getenv("LAMBDA_API_KEY")
        if not instance_id or not api_key:
            logger.warning("LAMBDA_INSTANCE_ID or LAMBDA_API_KEY missing, falling back")
            self._shutdown_generic()
            return

        try:
            resp = self.client.post(
                "https://cloud.lambdalabs.com/api/v1/instance-operations/terminate",
                json={"instance_ids": [instance_id]},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            logger.info("Lambda terminate response: HTTP %d", resp.status_code)
        except Exception as exc:
            logger.error("Lambda terminate failed: %s", exc)
            self._shutdown_generic()

    def _shutdown_vast(self):
        """Vast.ai instances are Docker-based; just stop the container."""
        logger.info("Vast.ai detected -- stopping container")
        self._shutdown_generic()

    @staticmethod
    def _shutdown_generic():
        """Last resort: system shutdown."""
        logger.info("Executing system shutdown")
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"], timeout=5)
        except Exception as exc:
            logger.error("System shutdown failed: %s", exc)
            logger.info("Exiting process -- cloud provider should reclaim instance")
            sys.exit(0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        return headers

    def _handle_signal(self, signum, frame):
        logger.info("Received signal %d, stopping...", signum)
        self.running = False


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

if __name__ == "__main__":
    monitor = FederationIdleMonitor()
    monitor.run()
