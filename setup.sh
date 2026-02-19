#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Unicorn Commander — Setup Script
# =============================================================================
# This script configures your environment and gets you running in minutes.
#
# Usage:
#   ./setup.sh          # Interactive setup
#   ./setup.sh --quick  # Accept defaults (dev mode, no billing)
# =============================================================================

BOLD="\033[1m"
DIM="\033[2m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

banner() {
  echo ""
  echo -e "${CYAN}${BOLD}"
  echo "  ╔══════════════════════════════════════════════════╗"
  echo "  ║           🦄 Unicorn Commander Setup             ║"
  echo "  ║      The Open-Source AI Cloud Platform           ║"
  echo "  ╚══════════════════════════════════════════════════╝"
  echo -e "${RESET}"
}

info()    { echo -e "${CYAN}ℹ${RESET}  $1"; }
success() { echo -e "${GREEN}✓${RESET}  $1"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $1"; }
error()   { echo -e "${RED}✗${RESET}  $1"; }

generate_secret() {
  # Generate a random 32-char alphanumeric string
  if command -v openssl &>/dev/null; then
    openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32
  else
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 32
  fi
}

# ---- Pre-flight checks ----

preflight() {
  local ok=true

  if ! command -v docker &>/dev/null; then
    error "Docker is not installed. Please install Docker first: https://docs.docker.com/get-docker/"
    ok=false
  fi

  if ! docker compose version &>/dev/null 2>&1 && ! docker-compose version &>/dev/null 2>&1; then
    error "Docker Compose is not installed. Please install Docker Compose: https://docs.docker.com/compose/install/"
    ok=false
  fi

  if ! command -v git &>/dev/null; then
    error "Git is not installed. Please install Git first."
    ok=false
  fi

  if [ "$ok" = false ]; then
    echo ""
    error "Please install the missing dependencies and try again."
    exit 1
  fi

  success "Docker, Docker Compose, and Git are installed"
}

# ---- Submodule init ----

init_submodules() {
  if [ ! -f "ops-center/README.md" ] || [ ! -f "unicorn-brigade/README.md" ]; then
    info "Initializing git submodules..."
    git submodule update --init --recursive
    success "Submodules initialized"
  else
    success "Submodules already initialized"
  fi
}

# ---- Environment setup ----

setup_env() {
  local quick="${1:-false}"

  if [ -f ".env" ]; then
    warn ".env file already exists"
    if [ "$quick" = "false" ]; then
      read -rp "  Overwrite? (y/N): " overwrite
      if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        info "Keeping existing .env"
        return
      fi
    else
      info "Quick mode: keeping existing .env"
      return
    fi
  fi

  info "Generating .env with secure random secrets..."

  local pg_pass
  local kc_pass
  local jwt_secret
  local ops_secret
  local brigade_secret
  local service_key

  pg_pass="$(generate_secret)"
  kc_pass="$(generate_secret)"
  jwt_secret="$(generate_secret)"
  ops_secret="$(generate_secret)"
  brigade_secret="$(generate_secret)"
  service_key="$(generate_secret)"

  cat > .env << EOF
# =============================================================================
# Unicorn Commander - Generated Configuration
# Generated on: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# =============================================================================

# --- PostgreSQL ---
POSTGRES_USER=unicorn
POSTGRES_PASSWORD=${pg_pass}
POSTGRES_HOST=unicorn-postgresql
POSTGRES_PORT=5432
OPS_CENTER_DB=unicorn_db
BRIGADE_DB=brigade_db

# --- Redis ---
REDIS_URL=redis://unicorn-redis:6379

# --- Keycloak SSO ---
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=${kc_pass}
KEYCLOAK_REALM=uchub
KEYCLOAK_URL=http://unicorn-keycloak:8080

# --- OAuth Clients (configure in Keycloak after first boot) ---
OPS_CENTER_CLIENT_ID=ops-center
OPS_CENTER_CLIENT_SECRET=${ops_secret}
BRIGADE_CLIENT_ID=brigade
BRIGADE_CLIENT_SECRET=${brigade_secret}

# --- Service Keys ---
BRIGADE_SERVICE_KEY=${service_key}
JWT_SECRET=${jwt_secret}

# --- Billing (disabled by default) ---
BILLING_ENABLED=false
# STRIPE_SECRET_KEY=sk_test_...
# STRIPE_PUBLISHABLE_KEY=pk_test_...

# --- LLM Providers (add your keys to enable AI features) ---
# OPENROUTER_API_KEY=sk-or-...
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
EOF

  success ".env created with secure random secrets"
}

# ---- Main ----

main() {
  local quick=false
  if [ "${1:-}" = "--quick" ]; then
    quick=true
  fi

  banner
  preflight
  init_submodules
  setup_env "$quick"

  echo ""
  echo -e "${BOLD}Starting Unicorn Commander...${RESET}"
  echo ""

  if docker compose version &>/dev/null 2>&1; then
    docker compose up -d
  else
    docker-compose up -d
  fi

  echo ""
  echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${RESET}"
  echo -e "${GREEN}${BOLD}  Unicorn Commander is starting up!${RESET}"
  echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${RESET}"
  echo ""
  echo -e "  ${BOLD}Services:${RESET}"
  echo -e "    Ops-Center:     ${CYAN}http://localhost:8084${RESET}"
  echo -e "    Brigade API:    ${CYAN}http://localhost:8112${RESET}"
  echo -e "    Brigade UI:     ${CYAN}http://localhost:3000${RESET}"
  echo -e "    Keycloak Admin: ${CYAN}http://localhost:8080${RESET}"
  echo ""
  echo -e "  ${BOLD}Keycloak:${RESET}"
  echo -e "    The ${CYAN}uchub${RESET} realm is auto-imported on first boot."
  echo -e "    Admin console: http://localhost:8080/admin/"
  echo -e "    Credentials are in your ${CYAN}.env${RESET} file."
  echo ""
  echo -e "  ${BOLD}Next steps:${RESET}"
  echo -e "    1. Wait ~30s for all services to be healthy"
  echo -e "    2. Open Keycloak and update OAuth client secrets to match .env"
  echo -e "    3. Configure identity providers (Google, GitHub, Microsoft)"
  echo -e "    4. Add your LLM API keys to .env for AI features"
  echo ""
  echo -e "  ${DIM}Run 'docker compose logs -f' to watch startup progress${RESET}"
  echo ""
}

main "$@"
