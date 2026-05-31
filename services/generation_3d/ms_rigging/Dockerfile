FROM python:3.11-slim

# Instalar dependencias de sistema mínimas para empaquetado de geometrías
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar uv para acelerar drásticamente los builds y la gestión de dependencias
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Instalar PyTorch CPU primero usando uv. Esto evita descargar dependencias CUDA de 4.5+ GB
RUN uv pip install --system --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt

COPY . .

# Comando de arranque para Celery Worker en la cola 'rigging'
CMD ["celery", "-A", "worker", "worker", "--loglevel=info", "--queues=rigging"]
