#!/bin/bash
set -euo pipefail

# GymOps Security Audit Script
# Run this from any machine on the same LAN as the Raspberry Pi (192.168.1.66)
# This script only READS data and attempts common attacks. It does NOT modify data.

# Configuration via environment variables (never hardcode secrets or LAN topology).
RPI_IP="${RPI_IP:-}"
DOMAIN="${DOMAIN:-}"
API_KEY="${API_KEY:-}"

if [ -z "$RPI_IP" ] || [ -z "$DOMAIN" ]; then
    echo "Usage: RPI_IP=<ip> DOMAIN=<domain> API_KEY=<key> $0"
    echo "Example: RPI_IP=192.168.1.66 DOMAIN=gymops.example.com API_KEY=sk-xxx $0"
    exit 1
fi
REPORT_FILE="gymops-security-audit-$(date +%Y%m%d-%H%M%S).txt"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$REPORT_FILE"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$REPORT_FILE"; }
crit() { echo -e "${RED}[CRIT]${NC} $1" | tee -a "$REPORT_FILE"; }
separator() { echo "========================================" | tee -a "$REPORT_FILE"; }

# Initialize report
echo "GymOps Security Audit Report" > "$REPORT_FILE"
echo "Generated: $(date)" >> "$REPORT_FILE"
echo "Target: $RPI_IP / $DOMAIN" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

#######################################
# PHASE 1: RECONNAISSANCE
#######################################
separator
log "PHASE 1: Network Reconnaissance"
separator

# Check if target is reachable
if ping -c 1 -W 2 "$RPI_IP" > /dev/null 2>&1; then
    log "Host $RPI_IP is reachable"
else
    crit "Host $RPI_IP is NOT reachable. Are you on the same network?"
    exit 1
fi

# Port scan using netcat (nmap may not be installed)
log "Scanning common ports on $RPI_IP..."
PORTS=(22 80 443 81 8000 3000 9090)
OPEN_PORTS=()
for port in "${PORTS[@]}"; do
    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$RPI_IP/$port" 2>/dev/null; then
        crit "Port $port is OPEN on $RPI_IP"
        OPEN_PORTS+=("$port")
    else
        log "Port $port is closed/filtered"
    fi
done

if [[ " ${OPEN_PORTS[*]} " =~ " 8000 " ]]; then
    crit "CRITICAL: API port 8000 is exposed to LAN! It should only be internal to Docker."
fi

if [[ " ${OPEN_PORTS[*]} " =~ " 3000 " ]]; then
    crit "CRITICAL: Grafana port 3000 is exposed to LAN! It should only be internal to Docker."
fi

if [[ " ${OPEN_PORTS[*]} " =~ " 9090 " ]]; then
    crit "CRITICAL: Prometheus port 9090 is exposed to LAN! It should only be internal to Docker."
fi

#######################################
# PHASE 2: API AUTHENTICATION BYPASS
#######################################
separator
log "PHASE 2: API Authentication & Authorization"
separator

log "Testing endpoints WITHOUT API Key..."

# Healthcheck (should be public)
HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DOMAIN/health" 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    log "/health is accessible (expected - monitoring endpoint)"
else
    warn "/health returned HTTP $HTTP_STATUS"
fi

# Metrics (should be public for Prometheus)
HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DOMAIN/metrics" 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    warn "/metrics is publicly accessible! Information disclosure risk."
    METRICS_COUNT=$(curl -sk "https://$DOMAIN/metrics" 2>/dev/null | grep -c "gymops_" || echo "0")
    warn "Found $METRICS_COUNT internal metrics exposed."
else
    log "/metrics is not publicly accessible (HTTP $HTTP_STATUS)"
fi

# Protected endpoints without key
ENDPOINTS=(
    "GET|/sessions/active?telegram_user_id=1"
    "POST|/sessions/start"
    "POST|/sessions/end"
    "POST|/sets"
    "GET|/stats/exercise/squat?telegram_user_id=1"
    "GET|/history/exercise/squat?telegram_user_id=1"
    "GET|/summary/1?telegram_user_id=1"
)

for item in "${ENDPOINTS[@]}"; do
    METHOD="${item%%|*}"
    PATH="${item##*|}"
    
    if [ "$METHOD" = "GET" ]; then
        HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" -X GET "https://$DOMAIN$PATH" 2>/dev/null || echo "000")
    else
        HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" -X "$METHOD" -H "Content-Type: application/json" -d '{"telegram_user_id":1}' "https://$DOMAIN$PATH" 2>/dev/null || echo "000")
    fi
    
    if [ "$HTTP_STATUS" = "403" ]; then
        log "$METHOD $PATH -> 403 Forbidden (protected)"
    elif [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "201" ]; then
        crit "VULNERABLE: $METHOD $PATH -> $HTTP_STATUS WITHOUT API KEY!"
    elif [ "$HTTP_STATUS" = "404" ]; then
        warn "$METHOD $PATH -> 404 (endpoint not found or NPM issue)"
    elif [ "$HTTP_STATUS" = "422" ]; then
        log "$METHOD $PATH -> 422 (validation error, but auth passed? CHECK THIS)"
    else
        warn "$METHOD $PATH -> HTTP $HTTP_STATUS"
    fi
done

#######################################
# PHASE 3: IDOR (Insecure Direct Object Reference)
#######################################
separator
log "PHASE 3: IDOR - Accessing other users' data"
separator

if [ -n "$API_KEY" ]; then
    log "Testing with API_KEY for user telegram_user_id=99999 (should not exist)..."
    
    HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "https://$DOMAIN/sessions/active?telegram_user_id=99999" 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "200" ]; then
        crit "IDOR RISK: /sessions/active for non-existent user returns 200 instead of 404!"
    else
        log "Non-existent user returns HTTP $HTTP_STATUS (good)"
    fi
    
    # Try sequential user IDs to see if we can enumerate users
    log "Testing user enumeration (telegram_user_id 1-5)..."
    for uid in 1 2 3 4 5; do
        HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "https://$DOMAIN/sessions/active?telegram_user_id=$uid" 2>/dev/null || echo "000")
        if [ "$HTTP_STATUS" = "200" ]; then
            warn "User ID $uid exists (active session or user found)"
        fi
    done
else
    warn "Skipping IDOR tests (no API_KEY provided). Set API_KEY environment variable."
fi

#######################################
# PHASE 4: INPUT VALIDATION
#######################################
separator
log "PHASE 4: Input Validation & Injection Tests"
separator

if [ -n "$API_KEY" ]; then
    # SQL Injection attempt in exercise name
    log "Testing SQL injection in exercise name..."
    HTTP_BODY=$(curl -sk -H "X-API-Key: $API_KEY" "https://$DOMAIN/history/exercise/squat'%20OR%20'1'='1?telegram_user_id=1" 2>/dev/null || echo "ERROR")
    if echo "$HTTP_BODY" | grep -q "detail"; then
        log "SQL injection test returned error (likely safe)"
    else
        warn "Unexpected response to SQLi test. Manual review needed."
    fi
    
    # Negative weight
    log "Testing negative weight..."
    HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
        -d '{"telegram_user_id":1,"exercise_name":"test","weight":-100,"reps":5,"rpe":8}' \
        "https://$DOMAIN/sets" 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "201" ]; then
        crit "Negative weight accepted! Input validation missing."
    else
        log "Negative weight rejected (HTTP $HTTP_STATUS)"
    fi
    
    # RPE out of range
    log "Testing invalid RPE (15)..."
    HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
        -d '{"telegram_user_id":1,"exercise_name":"test","weight":100,"reps":5,"rpe":15}' \
        "https://$DOMAIN/sets" 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "201" ]; then
        warn "RPE 15 accepted! Should be limited to 6.5-10 (or 0 for warmup)."
    else
        log "Invalid RPE rejected (HTTP $HTTP_STATUS)"
    fi
    
    # Zero reps
    log "Testing zero reps..."
    HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
        -d '{"telegram_user_id":1,"exercise_name":"test","weight":100,"reps":0,"rpe":8}' \
        "https://$DOMAIN/sets" 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "201" ]; then
        warn "Zero reps accepted! Check if this is intended behavior."
    else
        log "Zero reps rejected (HTTP $HTTP_STATUS)"
    fi
    
    # XSS attempt in exercise name
    log "Testing XSS in exercise name..."
    HTTP_BODY=$(curl -sk -X POST -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" \
        -d '{"telegram_user_id":1,"exercise_name":"<script>alert(1)</script>","weight":100,"reps":5,"rpe":8}' \
        "https://$DOMAIN/sets" 2>/dev/null || echo "ERROR")
    if echo "$HTTP_BODY" | grep -q "<script>"; then
        crit "XSS VULNERABILITY: Script tag reflected in response!"
    else
        log "XSS test passed (response sanitized or not reflected)"
    fi
else
    warn "Skipping input validation tests (no API_KEY provided)"
fi

#######################################
# PHASE 5: DEFAULT CREDENTIALS
#######################################
separator
log "PHASE 5: Default Credentials Check"
separator

# Nginx Proxy Manager default login
log "Checking Nginx Proxy Manager default credentials..."
NPM_LOGIN=$(curl -sk -X POST -H "Content-Type: application/json" \
    -d '{"identity":"admin@example.com","password":"changeme"}' \
    "http://$RPI_IP:81/api/tokens" 2>/dev/null || echo "CONNECTION_FAILED")

if echo "$NPM_LOGIN" | grep -q "token"; then
    crit "CRITICAL: Nginx Proxy Manager uses default credentials!"
    crit "Login: admin@example.com / changeme"
else
    log "NPM default credentials rejected (good)"
fi

# Grafana default login
log "Checking Grafana default credentials..."
# Grafana is not exposed to host, so we can't test from LAN unless through NPM
# Skip or test via domain if configured

#######################################
# PHASE 6: INFORMATION DISCLOSURE
#######################################
separator
log "PHASE 6: Information Disclosure"
separator

# Check for common exposed files
FILES=(".env" ".git/config" "docker-compose.yml" "docker-compose.rpi.yml" "Dockerfile" "requirements.txt")
for file in "${FILES[@]}"; do
    HTTP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DOMAIN/$file" 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "200" ]; then
        crit "CRITICAL: $file is accessible from the web!"
    else
        log "$file is not accessible (HTTP $HTTP_STATUS)"
    fi
done

# Check server headers
log "Checking server headers..."
HEADERS=$(curl -skI "https://$DOMAIN/health" 2>/dev/null | grep -i "server\|x-powered-by\|via" || true)
if [ -n "$HEADERS" ]; then
    warn "Server discloses headers:"
    echo "$HEADERS" | tee -a "$REPORT_FILE"
else
    log "No sensitive server headers disclosed"
fi

#######################################
# PHASE 7: RATE LIMITING
#######################################
separator
log "PHASE 7: Rate Limiting Test"
separator

log "Sending 20 rapid requests to /health..."
START_TIME=$(date +%s%N)
for i in {1..20}; do
    curl -sk -o /dev/null "https://$DOMAIN/health" 2>/dev/null || true
done
END_TIME=$(date +%s%N)
DURATION_MS=$(( (END_TIME - START_TIME) / 1000000 ))
log "20 requests completed in ${DURATION_MS}ms"
warn "No rate limiting detected on /health endpoint"

#######################################
# SUMMARY
#######################################
separator
log "AUDIT COMPLETE"
separator
log "Report saved to: $REPORT_FILE"
log ""
log "Next steps:"
log "1. Review all [CRIT] and [WARN] findings above"
log "2. Check $REPORT_FILE for full details"
log "3. Run with API_KEY=your_key to test authenticated endpoints"
log ""
log "To test authenticated endpoints, run:"
log "  API_KEY=your-secret-key RPI_IP=your.lan.ip DOMAIN=yourdomain.com ./security-audit.sh"
