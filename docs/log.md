# Registro de Errores e Incidencias (Log) - BioRender

Este archivo sirve para registrar de forma persistente cualquier error técnico, incidencia, advertencia de compilación o bug descubierto durante el desarrollo de **BioRender**, detallando su contexto, causa raíz y la solución implementada.

---

## Índice de Incidencias

| ID | Fecha | Componente | Descripción Corta | Estado |
|---|---|---|---|---|
| **INC-001** | 2026-05-28 | Infraestructura | Configuración e Inicialización de la Fase 0 | **Completado** |
| **INC-002** | 2026-05-28 | Frontend | Error [ERR_PNPM_IGNORED_BUILDS] durante pnpm install | **Completado** |
| **INC-003** | 2026-05-28 | IA / Pose | Incompatibilidad de MediaPipe con Python 3.14 | **Completado** |

---

## Historial Detallado de Incidencias

### INC-003: Incompatibilidad de MediaPipe con Python 3.14
*   **Fecha de Registro:** 2026-05-28
*   **Componente:** IA / Pose Detection / Python
*   **Descripción del Problema:** Al crear el entorno virtual de Python mediante `uv venv`, la instalación de `mediapipe==0.10.11` falló dado que no existen compilaciones de ruedas (wheels) de MediaPipe compatibles con la versión predeterminada del sistema de Python (v3.14.2).
*   **Causa Raíz:** MediaPipe sólo admite oficialmente versiones de Python desde 3.8 hasta 3.11.
*   **Solución Aplicada:**
    1.  Se forzó a `uv` a descargar e inicializar el entorno virtual específicamente con la versión Python 3.11 utilizando la directiva `uv venv --python 3.11`.
    2.  Se instalaron exitosamente todas las dependencias en segundos usando `uv pip install -r requirements.txt`.
*   **Estado:** Completado

### INC-002: Error [ERR_PNPM_IGNORED_BUILDS] durante pnpm install
*   **Fecha de Registro:** 2026-05-28
*   **Componente:** Frontend / Node / PNPM
*   **Descripción del Problema:** Al ejecutar `pnpm astro add react --yes`, la instalación automática falló con el código de error `ERR_PNPM_IGNORED_BUILDS` debido al bloqueo de scripts de compilación de `esbuild` y `sharp`.
*   **Causa Raíz:** Directivas de seguridad restrictivas de pnpm v11+ que ignoran scripts de compilación por defecto.
*   **Solución Aplicada:**
    1.  Se ejecutó el comando no interactivo `pnpm approve-builds --all` para aprobar y compilar todas las dependencias bloqueadas (`esbuild` y `sharp`) de forma permanente en el espacio de trabajo.
*   **Estado:** Completado

### INC-001: Configuración e Inicialización de la Fase 0
*   **Fecha de Registro:** 2026-05-28
*   **Componente:** Infraestructura / Setup
*   **Descripción del Problema:** Estructurar el monorepo y habilitar los manifiestos de dependencias iniciales (`package.json`, `Cargo.toml`, `requirements.txt`) garantizando compatibilidad con `pnpm`, `uv` y empaquetamiento Docker.
*   **Causa Raíz:** Configuración y scaffold inicial del monorepo.
*   **Solución Aplicada:**
    1.  Se estructuraron las carpetas base del proyecto (`frontend/`, `gateway/`, `services/realtime/ms_pose_rt/`).
    2.  Se inicializó la aplicación Astro 5 con React y TypeScript en `frontend/` mediante `pnpm`.
    3.  Se configuró el Gateway de Axum Rust y el microservicio FastAPI en Python.
    4.  Se escribió el runbook de ejecución definitivo en `docs/ejecucion.md`.
*   **Estado:** Completado
