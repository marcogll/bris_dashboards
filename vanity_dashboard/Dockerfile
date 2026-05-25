FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY vanity_dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vanity_common/ /app/vanity_common/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY vanity_dashboard/ /app/

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser
RUN chown -R appuser:appuser /app
USER appuser

ENV PORT=5002
EXPOSE 5002

CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "app:app"]