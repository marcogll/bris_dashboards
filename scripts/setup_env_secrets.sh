#!/bin/bash
# Genera .env.production con secret keys criptográficos para Coolify
# Uso: bash scripts/setup_env_secrets.sh

set -e
cd "$(dirname "$0")/.."

ENV_FILE=".env.production"

# Dominios
MAIN_DOMAIN="vanityhq.soul23.cloud"
EMPREQ_DOMAIN="vanityerq.soul23.cloud"

# Generar secret keys
HQ_SECRET=$(openssl rand -hex 32)
DASHBOARD_SECRET=$(openssl rand -hex 32)
PAYROLL_SECRET=$(openssl rand -hex 32)
ACTAS_SECRET=$(openssl rand -hex 32)
EMPREQ_SECRET=$(openssl rand -hex 32)
HRMGR_SECRET=$(openssl rand -hex 32)
HRMGR_DB_PASSWORD=$(openssl rand -hex 24)

cat > "$ENV_FILE" <<EOF
# ======================================================================
# VANITY HQ - PRODUCTION ENVIRONMENT FOR COOLIFY
# Generado: $(date '+%Y-%m-%d %H:%M:%S')
# Dominios: $MAIN_DOMAIN + $EMPREQ_DOMAIN
# ======================================================================

# === DOMINIOS ===
COOLIFY_DOMAIN=$MAIN_DOMAIN
MAIN_DOMAIN=$MAIN_DOMAIN
EMPREQ_DOMAIN=$EMPREQ_DOMAIN

# === URLs PÚBLICAS ===
VANITY_HQ_PUBLIC_URL=https://$MAIN_DOMAIN
VANITY_DASHBOARD_PUBLIC_URL=https://$MAIN_DOMAIN/dashboard
VANITY_HRMGR_PUBLIC_URL=https://$MAIN_DOMAIN/empleadas
VANITY_PAYROLL_PUBLIC_URL=https://$MAIN_DOMAIN/payroll
VANITY_ACTAS_PUBLIC_URL=https://$MAIN_DOMAIN/actas
VANITY_EMPREQ_PUBLIC_URL=https://$EMPREQ_DOMAIN
PAYROLL_PUBLIC_URL=https://$MAIN_DOMAIN/payroll

# === URLs INTERNAS (Docker Network) ===
VANITY_HQ_URL=http://hq-wrapper:5050
VANITY_DASHBOARD_URL=http://dashboard:5002
VANITY_HRMGR_URL=http://hrmgr-web:8000
VANITY_PAYROLL_URL=http://payroll:5051
VANITY_ACTAS_URL=http://actas:5052
VANITY_EMPREQ_URL=http://empreq:5053
PAYROLL_BASE_URL=http://payroll:5051

# === SECRET KEYS (Generadas automáticamente - NO CAMBIAR) ===
VANITY_HQ_SECRET_KEY=$HQ_SECRET
VANITY_DASHBOARD_SECRET_KEY=$DASHBOARD_SECRET
VANITY_PAYROLL_SECRET_KEY=$PAYROLL_SECRET
VANITY_ACTAS_SECRET_KEY=$ACTAS_SECRET
VANITY_EMPREQ_SECRET_KEY=$EMPREQ_SECRET
HRMGR_SECRET_KEY=$HRMGR_SECRET
HRMGR_DB_PASSWORD=$HRMGR_DB_PASSWORD
VANITY_HQ_TOKEN_MAX_AGE=43200

# === HR MANAGER (Django) ===
HRMGR_DEBUG=False
ALLOWED_HOSTS=$MAIN_DOMAIN,www.$MAIN_DOMAIN,$EMPREQ_DOMAIN,localhost
CSRF_TRUSTED_ORIGINS=https://$MAIN_DOMAIN,https://www.$MAIN_DOMAIN,https://$EMPREQ_DOMAIN
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true

# === OPCIONAL ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_ID=
EOF

echo "✅ $ENV_FILE generado con éxito"
echo "⚠️  AGREGAR a .gitignore si no está"
echo ""
echo "Contenido:"
grep -E "^[A-Z_]+=." "$ENV_FILE" | sed 's/\(SECRET_KEY\|PASSWORD\|TOKEN\)=.*/\1=***HIDDEN***/g'