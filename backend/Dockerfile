FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /app/data && chown app:app /app/data
COPY --chown=app:app backend/*.py ./backend/
# 초기 기획(ZEB) 데모: 하위 패키지와 규칙 YAML·샘플 데이터
COPY --chown=app:app backend/zeb/ ./backend/zeb/
COPY --chown=app:app frontend/public/samples/purchase-orders/ ./samples/purchase-orders/
USER app
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
