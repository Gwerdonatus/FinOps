FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md requirements.lock ./
COPY apps/ apps/
COPY config/ config/
ARG PIP_NO_INDEX=0
RUN --mount=type=bind,source=.wheel-cache,target=/wheels \
    pip install --no-cache-dir --find-links=/wheels -c requirements.lock setuptools wheel && \
    pip install --no-cache-dir --no-build-isolation --find-links=/wheels -c requirements.lock -e '.[dev]' gunicorn==23.0.0
COPY manage.py ./
COPY templates/ templates/
COPY static/ static/
COPY tests/ tests/
RUN useradd --uid 1001 --create-home appuser && mkdir -p media staticfiles && chown -R appuser:appuser /app
USER appuser
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120"]
