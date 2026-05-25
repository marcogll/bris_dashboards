# Seguridad — Cadrex

## Visión General

Cadrex implementa múltiples capas de seguridad:

1. **Autenticación local opt-in** — session-based, desactivada por defecto.
2. **Headers de seguridad HTTP** — CSP, HSTS, X-Frame, etc.
3. **Manejo seguro de secrets** — via variables de entorno.
4. **ProxyFix** — para operación segura detrás de reverse proxies.

---

## Autenticación Local

### Login Opt-in

La autenticación está **desactivada por defecto** (`LOGIN_REQUIRED=false`). Para activarla:

```env
LOGIN_REQUIRED=true
```

Cuando está activa, el decorador `@login_required` protege todas las rutas del dashboard y redirige a `/login` si no hay sesión activa.

### Gestión de Usuarios (`data/users.json`)

Los usuarios se almacenan en un archivo JSON local con contraseñas hasheadas via `werkzeug.security.generate_password_hash` (scrypt):

```json
{
  "adriana": {
    "password": "scrypt:32768:8:1$...",
    "display_name": "Adriana Ramos",
    "role": "admin"
  }
}
```

Roles soportados: `god`, `admin`, `viewer`.

**Advertencias**:
- `users.json` está en el repositorio para facilitar el despliegue inicial.
- En entornos multi-usuario sensibles, considerar migrar a base de datos.
- El archivo debe tener permisos restrictivos (`chmod 600`) en producción.

### Sesiones Flask

```python
app.secret_key = SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 8  # 8 horas
```

- Las sesiones usan cookies firmadas con `SECRET_KEY`.
- `session.permanent = True` al hacer login.
- Logout destruye la sesión (`session.clear()`).

### Secret Key

```python
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    # Fallback: genera clave estable basada en hostname + path
    base = f"{os.uname().nodename}-{BASE_DIR}"
    SECRET_KEY = hashlib.sha256(base.encode()).hexdigest()
```

**⚠️ Requerido en producción**: definir `SECRET_KEY` como variable de entorno. El fallback es conveniente para demos pero implica que las sesiones se invalidan si cambia el hostname o la ruta del contenedor.

Generar secret seguro:
```bash
openssl rand -hex 32
```

---

## Headers de Seguridad HTTP

### Content Security Policy (CSP)

```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "connect-src 'self' https://cdn.jsdelivr.net;"
)
```

**Justificación de directivas**:
- `style-src 'unsafe-inline'` — requerido por el theme toggle dinámico y estilos inline del layout.
- `script-src 'unsafe-inline'` — requerido por el widget de chat Bri AI y handlers inline del sidebar mobile.
- `connect-src 'self' https://cdn.jsdelivr.net` — permite fetch a CDNs para librerías de gráficos y al propio backend para el chat.
- `img-src 'self' data:` — soporta imágenes base64 inline (gráficos, logos).

**Mejoras futuras**:
- Implementar nonce CSP para eliminar `'unsafe-inline'` de scripts.
- Mover handlers inline a archivos JS externos.

### Headers Adicionales

| Header | Valor | Propósito |
|--------|-------|-----------|
| `X-Frame-Options` | `SAMEORIGIN` | Previene clickjacking |
| `X-Content-Type-Options` | `nosniff` | Evita MIME-sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limita leakage de referrer |

Nota: `Strict-Transport-Security` (HSTS) se delega a Traefik/Coolify en el edge.

---

## ProxyFix

```python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
```

Garantiza que Flask interprete correctamente:
- `X-Forwarded-For` — IP real del cliente.
- `X-Forwarded-Proto` — protocolo original (HTTPS).
- `X-Forwarded-Host` — host original.
- `X-Forwarded-Prefix` — prefijo de ruta (para path-based routing).

Esto es crítico para que `url_for` genere URLs correctas detrás de Traefik y para la seguridad de cookies.

---

## Validación de Inputs

### Upload de CSV

- Ruta: `/upload` (protegida por `UPLOAD_SECRET` opcional).
- Validación: solo archivos `.csv`, tamaño limitado por el servidor web.
- El secret se compara contra la variable de entorno; si está vacío, el upload está deshabilitado.

### Datasets Curados (`/datos/upload/<name>`)

- Validación de nombre contra whitelist (`CURATED_DATASETS`).
- Parsing de CSV con validación de columnas esperadas.
- Logging de quién actualizó qué dataset (`session.get("user", "anon")`).

### Chat AI (`/api/chat`)

- Rate limiting implícito vía Gunicorn workers y timeout.
- Validación de presencia de `OPENROUTER_API_KEY` antes de enviar request.
- No se almacenan conversaciones en el servidor.

---

## Recomendaciones de Producción

### Secrets

1. Nunca commitear `.env` o `.env.coolify` con valores reales.
2. Rotar `SECRET_KEY` periódicamente.
3. Usar gestor de secrets de Coolify o un vault externo.

### Red

1. Mantener MySQL accesible solo dentro de la red Docker interna (no exponer puertos host).
2. Usar firewall de cloud (Cloudflare, AWS Security Groups) para restringir acceso al VPS.

### Dependencias

1. Actualizar imágenes base (`python:3.12-slim`, `mysql:8.4`) periódicamente.
2. Revisar vulnerabilidades con `pip-audit` o `safety`.

### Backup

1. Volumen `cadrex_mysql_data`: backup diario via snapshot de VPS o `mysqldump`.
2. Volumen `./data`: incluir en backup de repositorio o snapshot.

---

## Checklist de Seguridad Pre-Deploy

- [ ] `SECRET_KEY` definida y con alta entropía (≥256 bits).
- [ ] `LOGIN_REQUIRED` configurado según el entorno.
- [ ] `UPLOAD_SECRET` definida si se habilita upload de CSV.
- [ ] `MYSQL_PASSWORD` y `MYSQL_ROOT_PASSWORD` son fuertes y únicas.
- [ ] `OPENROUTER_API_KEY` no está expuesta en logs ni en el repo.
- [ ] `.env` y `.env.coolify` están en `.gitignore`.
- [ ] `users.json` tiene permisos `600` en el contenedor/host.
- [ ] SSL/TLS activo en Traefik/Coolify (Let's Encrypt).
- [ ] Healthchecks no exponen información sensible.
- [ ] Logs no contienen passwords ni tokens.
