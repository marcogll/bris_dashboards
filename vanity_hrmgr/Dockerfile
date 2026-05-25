FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY vanity_hrmgr/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /install /usr/local
COPY vanity_common/ /app/vanity_common/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY vanity_hrmgr/ /app/
COPY vanity_hrmgr/entrypoint.sh /app/entrypoint.sh
RUN mkdir -p logs
RUN python manage.py collectstatic --noinput || true
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "config.wsgi:application"]