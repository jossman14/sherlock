# Konteks build = akar repo, supaya paket sherlock_project dipasang dari fork ini
# (bukan dari PyPI) — perubahan apa pun di fork ikut terpakai.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md* ./
COPY sherlock_project ./sherlock_project
COPY docs ./docs
RUN pip install --no-cache-dir . && pip install --no-cache-dir "fastapi==0.115.6" "uvicorn[standard]==0.34.0"

COPY web/api /app/web/api
WORKDIR /app/web/api

# Berjalan sebagai non-root: proses ini menembak ratusan situs luar, jadi jangan beri
# hak lebih dari yang dibutuhkan.
RUN useradd -m -u 10001 sherlock && chown -R sherlock /app
USER sherlock

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120"]
