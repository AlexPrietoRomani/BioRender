# Guía de Ejecución y Despliegue: BioRender MVP

> **Proyecto:** `BioRender - Plataforma de Retargeting y Captura de Movimiento RT`
> **Fecha de Actualización:** 2026-05-28
> **Objetivo:** Este documento sirve como la guía definitiva paso a paso (runbook) para que cualquier desarrollador pueda clonar, levantar el entorno local de desarrollo del MVP, compilar y verificar el proyecto sin fricciones.

---

## 1. Requisitos Previos

Antes de comenzar, asegúrate de tener instalado el siguiente software y herramientas en tu sistema operativo:

### 1.1 Software y Herramientas

| Software | Versión Mínima | Comando de Verificación |
|----------|---------------|-------------------------|
| Node.js  | 20.x+         | `node --version`        |
| PNPM     | 9.x+          | `pnpm --version`        |
| Rust / Cargo | 1.78+     | `cargo --version`       |
| Python   | 3.10          | `python --version`      |
| UV (Python tool) | Latest | `uv --version`          |
| Docker & Compose | Latest | `docker compose version`|
| Git      | 2.30+         | `git --version`         |

---

## 2. Instalación Local

Sigue estos pasos detallados para levantar el repositorio y configurar todos los servicios de forma unificada.

### 2.1 Preparar Entorno de la IA (Backend Python)

El microservicio de pose utiliza `uv` para la máxima velocidad y aislamiento del entorno de desarrollo de Python.

```bash
# Entrar al directorio del microservicio de pose
cd services/realtime/ms_pose_rt

# Crear y activar el entorno virtual con uv
uv venv

# En Windows (PowerShell) activar el entorno:
.venv\Scripts\Activate.ps1

# Instalar dependencias utilizando uv
uv pip install -r requirements.txt

# Regresar a la raíz
cd ../../..
```

### 2.2 Instalar Dependencias del Frontend

La interfaz web del MVP (Astro + React) se inicializa a través de `pnpm`.

```bash
# Entrar al directorio del frontend
cd frontend

# Instalar dependencias con pnpm
pnpm install

# Regresar a la raíz
cd ..
```

### 2.3 Configuración de Variables de Entorno

Clona la plantilla de variables de entorno para el Gateway y el Frontend:

```bash
# Copiar plantilla
cp .env.example .env
```

---

## 3. Ejecución en Desarrollo

Puedes iniciar el stack completo de desarrollo del MVP utilizando Docker Compose o de forma manual aislando componentes.

### 3.1 Opción A: Despliegue con Docker Compose (Recomendado)

Esta opción compila el Gateway en Rust y levanta la API de Python de forma automática:

```bash
# Iniciar y compilar los contenedores locales
docker-compose up --build
```

### 3.2 Opción B: Ejecución Manual en Desarrollo (Terminales Separadas)

Útil para depuración y ciclos de recarga ultrarrápidos.

**Terminal 1 — Microservicio de Pose (Python FastAPI):**
```bash
cd services/realtime/ms_pose_rt
.venv\Scripts\Activate.ps1
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

**Terminal 2 — API Gateway (Rust Axum):**
```bash
cd gateway
cargo run
```

**Terminal 3 — Frontend Web (Astro):**
```bash
cd frontend
pnpm run dev
```

### 3.3 Puertos y Accesos Locales

*   **Frontend (Astro Web App):** [http://localhost:4321](http://localhost:4321)
*   **API Gateway (Rust HTTP/WS):** [http://localhost:8080](http://localhost:8080)
*   **Pose Inferencia API (FastAPI):** [http://localhost:8001](http://localhost:8001)
*   **Documentación API (Swagger):** [http://localhost:8001/docs](http://localhost:8001/docs)

### 3.4 Checklist de Verificación Rápida (Sanity Check)

1.  [ ] Acceder a `http://localhost:4321` y visualizar la página de aterrizaje del MVP con estética "BioRender Punk" (Dark-first, tipografía mono).
2.  [ ] Comprobar que la consola del navegador no contiene errores de carga de WebGL.
3.  [ ] Realizar una petición a `http://localhost:8001/health` y validar respuesta JSON `{ "status": "ok" }`.
4.  [ ] Conceder permisos de cámara web en la UI y comprobar la conexión activa del WebSocket en la pestaña de red (Network) de la consola del desarrollador.

---

## 4. Compilación y Build (Producción)

Pasos para compilar y empaquetar los estáticos y binarios nativos del MVP.

### 4.1 Compilación de Estáticos / Frontend
```bash
cd frontend
pnpm run build
```

### 4.2 Compilación del API Gateway (Rust)
```bash
cd gateway
cargo build --release
```

---

## 5. Troubleshooting (Solución de Problemas Frecuentes)

| Problema / Mensaje de Error | Causa Probable | Solución / Workaround |
|-----------------------------|----------------|-----------------------|
| `Connection refused` a `8001` | FastAPI apagado | Ejecutar `.venv\Scripts\Activate.ps1` e iniciar con `uvicorn main:app --port 8001`. |
| Errores de tipado TypeScript | Tipado R3F obsoleto | Correr `pnpm install` para actualizar paquetes en el directorio de `frontend/`. |
| Falla al cargar WebGL en R3F | Hardware sin soporte WebGL | Activar aceleración por hardware en los ajustes del navegador web. |

---

## 6. Ejecución de Tests

Comandos rápidos para correr pruebas de la lógica matemática del Gateway y de la inferencia.

```bash
# Correr pruebas unitarias de cinemática matemática de Rust (glam)
cd gateway
cargo test

# Correr pruebas unitarias de inferencia MediaPipe en Python
cd services/realtime/ms_pose_rt
pytest tests/
```
