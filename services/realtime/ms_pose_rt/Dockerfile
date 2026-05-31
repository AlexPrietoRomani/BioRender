FROM python:3.11-slim

# Instalar dependencias de sistema mínimas necesarias para OpenCV y MediaPipe
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

EXPOSE 8001

# Configuración de variables de entorno para optimizar hilos en CPU,
# reduciendo drásticamente el uso de memoria ram y el contexto de CPU.
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

