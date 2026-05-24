FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY vanity_empreq/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vanity_common/ /app/vanity_common/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY vanity_empreq/ /app/

ENV PORT=5053
EXPOSE 5053

CMD ["gunicorn", "--bind", "0.0.0.0:5053", "--workers", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "app:app"]