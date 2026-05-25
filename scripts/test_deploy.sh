#!/bin/bash
# ======================================================================
# VANITY HQ - TEST DE DESPLIEGUE PARA 2 DOMINIOS
# vanityhq.soul23.cloud (Admin) + vanityerq.soul23.cloud (Empleadas)
# Uso: bash scripts/test_deploy.sh [local|remote]
# ======================================================================

set +e

MODE="${1:-remote}"
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
BLUE='\033[94m'
RESET='\033[0m'

PASS=0
FAIL=0
WARN=0

check() {
    local desc="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local curl_args=""
    
    if [ "$MODE" = "remote" ]; then
        curl_args="-sk --max-time 10"
    else
        curl_args="-s -H 'X-Forwarded-Proto: https' --max-time 5"
    fi
    
    status=$(eval curl $curl_args -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$status" = "000" ]; then
        echo -e "  ${RED}FAIL${RESET} $desc → Connection refused"
        ((FAIL++))
    elif [ "$status" = "$expected_status" ]; then
        echo -e "  ${GREEN}PASS${RESET} $desc → $status"
        ((PASS++))
    else
        echo -e "  ${YELLOW}WARN${RESET} $desc → Expected $expected_status, got $status"
        ((WARN++))
    fi
}

check_redirect() {
    local desc="$1"
    local url="$2"
    local expected_location="$3"
    local curl_args=""
    
    if [ "$MODE" = "remote" ]; then
        curl_args="-sk --max-time 10"
    else
        curl_args="-s -H X-Forwarded-Proto:https --max-time 5"
    fi
    
    location=$(eval curl $curl_args -o /dev/null -w "%{redirect_url}" "$url" 2>/dev/null || echo "")
    status=$(eval curl $curl_args -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$status" = "000" ]; then
        echo -e "  ${RED}FAIL${RESET} $desc → Connection refused"
        ((FAIL++))
    elif echo "$location" | grep -q "$expected_location"; then
        echo -e "  ${GREEN}PASS${RESET} $desc → Redirects to $location"
        ((PASS++))
    else
        echo -e "  ${YELLOW}WARN${RESET} $desc → Status $status, redirect: ${location:-none}"
        ((WARN++))
    fi
}

check_contains() {
    local desc="$1"
    local url="$2"
    local search="$3"
    local curl_args=""
    
    if [ "$MODE" = "remote" ]; then
        curl_args="-skL --max-time 10"
    else
        curl_args="-sL -H X-Forwarded-Proto:https --max-time 5"
    fi
    
    body=$(eval curl $curl_args "$url" 2>/dev/null || echo "")
    
    if echo "$body" | grep -q "$search"; then
        echo -e "  ${GREEN}PASS${RESET} $desc → Found '$search'"
        ((PASS++))
    else
        echo -e "  ${RED}FAIL${RESET} $desc → '$search' not found in response"
        ((FAIL++))
    fi
}

if [ "$MODE" = "local" ]; then
    HQ="http://localhost"
    DASHBOARD="http://localhost/dashboard"
    HRMGR="http://localhost/empleadas"
    PAYROLL="http://localhost/payroll"
    ACTAS="http://localhost/actas"
    EMPREQ="http://localhost/empreq"
    echo -e "${BLUE}=== TEST LOCAL (nginx :80) ===${RESET}"
else
    HQ="https://vanityhq.soul23.cloud"
    DASHBOARD="https://vanityhq.soul23.cloud/dashboard"
    HRMGR="https://vanityhq.soul23.cloud/empleadas"
    PAYROLL="https://vanityhq.soul23.cloud/payroll"
    ACTAS="https://vanityhq.soul23.cloud/actas"
    EMPREQ="https://vanityerq.soul23.cloud"
    echo -e "${BLUE}=== TEST REMOTO (2 dominios) ===${RESET}"
fi

echo ""
echo -e "${BLUE}1. DNS RESOLUTION${RESET}"
if [ "$MODE" = "remote" ]; then
    for domain in vanityhq.soul23.cloud vanityerq.soul23.cloud; do
        ip=$(dig +short "$domain" A 2>/dev/null | head -1)
        if [ -n "$ip" ]; then
            echo -e "  ${GREEN}PASS${RESET} $domain → $ip"
            ((PASS++))
        else
            echo -e "  ${RED}FAIL${RESET} $domain → No DNS resolution"
            ((FAIL++))
        fi
    done
else
    echo -e "  ${YELLOW}SKIP${RESET} DNS check en modo local"
fi

echo ""
echo -e "${BLUE}2. HEALTH CHECKS (healthz)${RESET}"
check "HQ Wrapper" "$HQ/healthz"
check "Dashboard" "$DASHBOARD/healthz"
check "Payroll" "$PAYROLL/healthz"
check "Actas" "$ACTAS/healthz"
check "EmpReq" "$EMPREQ/healthz"

if [ "$MODE" = "remote" ]; then
    echo ""
    echo -e "${BLUE}3. SSL / HTTPS${RESET}"
    for url in "$HQ" "$EMPREQ"; do
        domain=$(echo "$url" | sed 's|https://||')
        cert_info=$(echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | openssl x509 -noout -subject -dates 2>/dev/null || echo "")
        if [ -n "$cert_info" ]; then
            echo -e "  ${GREEN}PASS${RESET} SSL cert for $domain"
            echo "    $(echo "$cert_info" | head -2 | tr '\n' ' ')"
            ((PASS++))
        else
            echo -e "  ${RED}FAIL${RESET} No SSL cert for $domain"
            ((FAIL++))
        fi
    done
else
    echo ""
    echo -e "${YELLOW}3. SSL / HTTPS → SKIP (modo local)${RESET}"
fi

echo ""
echo -e "${BLUE}4. AUTH / LOGIN PAGES${RESET}"
check_contains "HQ Login page" "$HQ/" "login"
check_contains "EmpReq Login page" "$EMPREQ/" "login"

echo ""
echo -e "${BLUE}5. SSO TOKEN FLOW (HQ → Sub-apps)${RESET}"
if [ "$MODE" = "remote" ]; then
    # Test that /auth/hq endpoint exists on each sub-service
    for svc_name in "Payroll" "Actas" "EmpReq"; do
        case $svc_name in
            Payroll) svc_url="$PAYROLL" ;;
            Actas) svc_url="$ACTAS" ;;
            EmpReq) svc_url="$EMPREQ" ;;
        esac
        status=$(curl -sk --max-time 10 -o /dev/null -w "%{http_code}" "$svc_url/auth/hq?token=invalid" 2>/dev/null || echo "000")
        if [ "$status" != "000" ]; then
            echo -e "  ${GREEN}PASS${RESET} $svc_name /auth/hq endpoint reachable ($status)"
            ((PASS++))
        else
            echo -e "  ${RED}FAIL${RESET} $svc_name /auth/hq endpoint unreachable"
            ((FAIL++))
        fi
    done
else
    echo -e "  ${YELLOW}SKIP${RESET} SSO flow en modo local (requires valid token)"
fi

echo ""
echo -e "${BLUE}6. CROSS-DOMAIN COOKIES (2 dominios)${RESET}"
if [ "$MODE" = "remote" ]; then
    # Check that HQ sets cookies for vanityhq.soul23.cloud
    hq_cookies=$(curl -sk --max-time 10 -D - "$HQ/" 2>/dev/null | grep -i "set-cookie" || echo "")
    if echo "$hq_cookies" | grep -qi "domain=.*vanityhq"; then
        echo -e "  ${GREEN}PASS${RESET} HQ cookie domain = vanityhq.soul23.cloud"
        ((PASS++))
    else
        echo -e "  ${YELLOW}WARN${RESET} HQ cookie domain not set for vanityhq (may be default)"
        ((WARN++))
    fi
    
    empreq_cookies=$(curl -sk --max-time 10 -D - "$EMPREQ/" 2>/dev/null | grep -i "set-cookie" || echo "")
    if echo "$empreq_cookies" | grep -qi "domain=.*vanityerq"; then
        echo -e "  ${GREEN}PASS${RESET} EmpReq cookie domain = vanityerq.soul23.cloud"
        ((PASS++))
    else
        echo -e "  ${YELLOW}WARN${RESET} EmpReq cookie domain not set for vanityerq"
        ((WARN++))
    fi
else
    echo -e "  ${YELLOW}SKIP${RESET} Cross-domain cookies en modo local"
fi

echo ""
echo -e "${BLUE}7. DASHBOARD / HRMGR (rutas path-based)${RESET}"
check "Dashboard route" "$DASHBOARD/" 302
check "HRMGR route" "$HRMGR/" 301
check "Payroll route" "$PAYROLL/" 302
check "Actas route" "$ACTAS/" 302

echo ""
echo -e "${BLUE}===========================================${RESET}"
echo -e "${GREEN}PASS: $PASS${RESET}  ${RED}FAIL: $FAIL${RESET}  ${YELLOW}WARN: $WARN${RESET}"
echo -e "${BLUE}===========================================${RESET}"

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}❌ HAY ERRORES - revisar antes de mostrar a tu jefe${RESET}"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Funcional con advertencias - revisar los WARN${RESET}"
    exit 0
else
    echo -e "${GREEN}✅ TODO PASÓ - listo para la demo${RESET}"
    exit 0
fi