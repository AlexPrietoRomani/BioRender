FROM nvidia/cuda:12.4.0-cudnn9-runtime-ubuntu22.04

# Configurar variables no interactivas para apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias básicas del sistema y librerías requeridas por Blender y Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    xz-utils \
    libxi6 \
    libxxf86vm6 \
    libxrender1 \
    libgl1-mesa-glx \
    libgl1 \
    libglu1-mesa \
    libxkbcommon0 \
    libsm6 \
    libxext6 \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Descargar e instalar Blender 4.1.0 Headless
RUN curl -L -o blender.tar.xz https://download.blender.org/release/Blender4.1/blender-4.1.0-linux-x64.tar.xz \
    && tar -xvf blender.tar.xz --strip-components=1 -C /usr/local/bin \
    && rm blender.tar.xz

# Crear entorno virtual de Python e instalar requerimientos
RUN python3 -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comando de arranque para Celery Worker escuchando en la cola 'render'
CMD ["celery", "-A", "worker", "worker", "--loglevel=info", "--queues=render"]
