FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir build && python -m build --wheel

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SERVICEPILOT_DATA_DIR=/data
RUN groupadd --gid 10001 servicepilot && useradd --uid 10001 --gid 10001 --create-home servicepilot \
    && mkdir /data && chown servicepilot:servicepilot /data
WORKDIR /app
COPY requirements.lock ./
COPY --from=builder /build/dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps /tmp/*.whl && rm /tmp/*.whl
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"
CMD ["servicepilot", "serve", "--host", "0.0.0.0", "--port", "8000"]
