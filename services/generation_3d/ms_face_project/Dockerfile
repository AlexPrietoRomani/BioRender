# Dockerfile para el Microservicio de Proyección Facial CPU (MS 3.5)
FROM python:3.10-slim

# Evitar escritura de archivos pyc y habilitar logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema mínimas requeridas por OpenCV y MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias usando pip cacheado
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del microservicio
COPY . .

# Comando de inicio del worker Celery escuchando en la cola 'generation'
CMD ["celery", "-A", "worker", "worker", "--loglevel=info", "--queues=generation"]
