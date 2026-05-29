FROM python:3.11-slim

# Instalar dependencias de sistema mínimas necesarias para OpenCV y MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar PyTorch CPU primero. Esto es un truco de optimización crítico para evitar
# que MediaPipe descargue la versión de PyTorch habilitada para CUDA/NVIDIA,
# ahorrando de inmediato más de 4.5 GB de peso en la imagen final.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

# Configuración de variables de entorno para optimizar hilos en CPU,
# reduciendo drásticamente el uso de memoria ram y el contexto de CPU.
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
