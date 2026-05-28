# Listado de Tareas - BioRender Producción Completa (Microservicios)

> **Fuentes de contexto obligatorias:**
> - Plan Completo de Microservicios: [`docs/plan/plan_completo.md`](../plan/plan_completo.md)
> - Diagramas de Arquitectura: [`docs/architecture/arquitectura_biorender.md`](../architecture/arquitectura_biorender.md)
>
> **Convenciones de ID:**
> - **Fase:** `F{n}` — ej. `F0` (Setup e Infraestructura de Soporte)
> - **Sub Fase:** `SF{f}.{s}` — ej. `SF0.1`
> - **Tarea:** `T{f}.{s}.{t}` — ej. `T0.1.1`
> - **Acción:** `A{f}.{s}.{t}.{a}` — ej. `A0.1.1.1`

---

## Índice

- [Fase 0 — Setup e Infraestructura de Soporte Completa](#fase-0--setup-e-infraestructura-de-soporte-completa)
- [Fase 1 — Pipeline A: Generación 3D Asíncrona (Imágenes a GLB Rigged)](#fase-1--pipeline-a-generacion-3d-asincrona-imagenes-a-glb-rigged)
- [Fase 2 — Pipeline B: Renderizado Offline de Video (Blender Headless)](#fase-2--pipeline-b-renderizado-offline-de-video-blender-headless)
- [Fase 3 — API Gateway Completo, Colas y Almacenamiento S3](#fase-3--api-gateway-completo-colas-y-almacenamiento-s3)
- [Fase 4 — Frontend Unificado de Producción y Paneles Reactivos](#fase-4--frontend-unificado-de-produccion-y-paneles-reactivos)

---

## [ ] Fase 0 — Setup e Infraestructura de Soporte Completa

- **Objetivo:** Configurar y levantar la infraestructura asíncrona robusta (Redis, Object Storage MinIO y red Docker con aceleración GPU NVIDIA CUDA) para la ejecución en producción de los microservicios distribuidos.
- **AC global de la Fase:**
  - Los contenedores de soporte corren de manera persistente con volúmenes nombrados.
  - La red interna de Docker tiene visibilidad directa de las GPUs de la máquina local.

---

### [ ] Sub Fase 0.1 — Configuración de MinIO, Redis y GPU Docker Integration

- **Objetivo:** Disponer de los entornos físicos y variables unificadas para el monorepo en producción.
- **AC global de la Sub Fase:** Pruebas de conectividad y subida a MinIO mediante scripts asíncronos finalizan con éxito.

#### [ ] T0.1.1 — Inicialización de MinIO y Buckets S3
- **Objetivo:** Levantar e instrumentar el motor de almacenamiento compatible con S3.
- **AC:** Bucket `biorender-assets` creado y accesible de forma cifrada/pública para descargas directas.

##### [ ] A0.1.1.1 — Orquestación Docker Compose de Soporte
- **Objetivo:** Escribir el manifiesto unificado de infraestructura local.
- **Input:** Compose MVP.
- **Output:** Archivo `docker-compose.yml` completo con servicios de `redis` y `minio`.
- **Proceso:**
  - Agregar servicio `redis:7-alpine` con persistencia en volumen `redis_data`.
  - Agregar servicio `minio/minio:latest` exponiendo puerto API `9000` y consola `9001`, con volumen de datos persistente.
- **Tests:** Ejecutar `docker-compose up -d minio redis`.
- **AC:** Ambos contenedores responden a ping en sus respectivos puertos locales de red.

##### [ ] A0.1.1.2 — Setup Automatizado del Bucket S3
- **Objetivo:** Inicializar las políticas del bucket de MinIO en tiempo de arranque.
- **Input:** MinIO activo en puerto 9000.
- **Output:** Script en Python `scripts/setup_minio.py` con directivas boto3.
- **Proceso:**
  - Escribir script de comprobación y creación del bucket `biorender-assets` con políticas CORS laxas para habilitar subidas directas desde el navegador del cliente.
- **Tests:** Ejecutar `python scripts/setup_minio.py`.
- **AC:** El script imprime `Bucket creado y configurado con éxito` y finaliza en código 0.

---

## [ ] Fase 1 — Pipeline A: Generación 3D Asíncrona (Imágenes a GLB Rigged)

- **Objetivo:** Programar y desplegar secuencialmente los workers Celery de GPU que transforman una imagen estática 2D en un archivo humanoid `.glb` texturizado y estructurado con un armature óseo de 25 joints.
- **AC global de la Fase:** Un Job insertado en la cola `queue:generation` genera el archivo binario `.glb` en MinIO en menos de 30 segundos y lo valida sin advertencias técnicas estructurales.

---

### [ ] Sub Fase 1.1 — Multi-vista Diffusion Worker (MS 3.1)

- **Objetivo:** Inferencia del modelo de difusión Zero123++ para generar 6 vistas angulares consistentes.
- **AC global de la Sub Fase:** Carga y ejecución del modelo en GPU a partir de imágenes de entrada.

#### [ ] T1.1.1 — Worker Celery de Difusión
- **Objetivo:** Construir e instrumentar el worker distribuidor de tareas de imagen.
- **AC:** Generación de 6 imágenes multi-vista válidas.

##### [ ] A1.1.1.1 — Codificación del Worker Zero123++ (Python)
- **Objetivo:** Escribir la lógica Celery de inferencia en Python.
- **Input:** Tarea JSON `{ "job_id": "...", "image_key": "..." }`.
- **Output:** Módulo `services/generation_3d/ms_multiview/worker.py` y carga de pesos en PyTorch.
- **Proceso:**
  - Cargar el modelo difusor `Zero123++` en GPU.
  - Descargar imagen de MinIO, preprocesar y ejecutar inferencia a 6 ángulos constantes.
  - Subir resultados en formato PNG a la ruta `multiview/view_*.png` en MinIO y encadenar tarea de reconstrucción.
- **Tests:** Ejecutar la prueba con la imagen de fixture canónica.
- **AC:** Generación exitosa de las 6 vistas y guardado en MinIO en $< 5$ segundos.

---

### [ ] Sub Fase 1.2 — Reconstructor de Malla 3DGS (MS 3.2)

- **Objetivo:** Reconstrucción tridimensional mediante InstantMesh / LGM feed-forward.
- **AC global de la Sub Fase:** Malla texturizada (`model.obj` + `texture.png`) extraída de forma regular en GPU.

#### [ ] T1.2.1 — Worker de Reconstrucción Geométrica
- **Objetivo:** Programar el worker de extracción 3D feed-forward.
- **AC:** OBJ y PNG generados correctamente.

##### [ ] A1.2.1.1 — Codificación del Worker InstantMesh
- **Objetivo:** Escribir la inferencia de InstantMesh en Python.
- **Input:** 6 imágenes de la sub fase anterior.
- **Output:** Módulo `services/generation_3d/ms_reconstruction/worker.py`.
- **Proceso:**
  - Descargar las 6 vistas de la etapa previa de MinIO.
  - Ejecutar inferencia InstantMesh para obtener los Gaussians y la nube de puntos densa.
  - Aplicar Marching Cubes para extraer la malla `.obj` y proyectar la textura UV sobre `texture.png`.
  - Subir resultados al bucket de MinIO en la ruta `mesh/`.
- **Tests:** Ejecutar inferencia unitaria sobre el output multi-vista canónico.
- **AC:** Malla OBJ generada contiene mapeo UV válido y topología cerrada.

---

### [ ] Sub Fase 1.3 — Auto-Rigging Neuronal (MS 3.3)

- **Objetivo:** Incorporar armature adaptable y skinning weights mediante grafos neuronales.
- **AC global de la Sub Fase:** Modelo rigged exportado a formato FBX con pesos de piel válidos y jerarquía humanoid.

#### [ ] T1.3.1 — Worker de Rigging Adaptativo
- **Objetivo:** Programar el worker de rigging estructural.
- **AC:** FBX y JSON del esqueleto generados de manera consistente.

##### [ ] A1.3.1.1 — Codificación del Worker de Rigging (RigNet)
- **Objetivo:** Escribir la lógica de rigging y skinning en Python.
- **Input:** Malla `.obj` de la etapa anterior de MinIO.
- **Output:** Módulo `services/generation_3d/ms_rigging/worker.py`.
- **Proceso:**
  - Descargar y analizar topología de la malla tridimensional.
  - Predecir los 25 joints humanoid del esqueleto estándar y generar la armature jerárquica.
  - Calcular los skinning weights por vértice usando Linear Blend Skinning (LBS).
  - Exportar a `{job_id}/rigged/model_rigged.fbx` y el esqueleto JSON a `{job_id}/rigged/skeleton.json`.
- **Tests:** Ejecutar test unitario con una malla de prueba.
- **AC:** El script de verificación confirma que todos los pesos de skin por vértice suman exactamente 1.0.

---

### [ ] Sub Fase 1.4 — Ensamblador de Assets 3D (MS 3.4)

- **Objetivo:** Compilar e instrumentar el empaquetador final de assets `.glb` escrito en Rust para máxima eficiencia.
- **AC global de la Sub Fase:** Archivos binarios `.glb` auto-contenidos, compactos y optimizados para WebGL subidos a MinIO.

#### [ ] T1.4.1 — Compilador GLTF/GLB en Rust
- **Objetivo:** Programar el módulo de empaquetado tridimensional.
- **AC:** Binario de Rust compila y procesa en microsegundos.

##### [ ] A1.4.1.1 — Codificación del Ensamblador en Rust
- **Objetivo:** Escribir la lógica de conversión FBX+Textura a GLB usando el crate `gltf` de Rust.
- **Input:** FBX rigged, textura PNG y esqueleto JSON.
- **Output:** Módulo Rust compile-ready en `services/generation_3d/ms_asset_assembly/`.
- **Proceso:**
  - Parsear los buffers del FBX y re-indexar geometría.
  - Escribir buffers binarios en formato GLB conteniendo vértices, normales, UVs, joints y weights.
  - Incrustar la imagen de textura base PNG y serializar jerarquía de nodos óseos.
  - Subir binario auto-contenido resultante a MinIO en `final/avatar.glb`.
- **Tests:** Compilar y ejecutar test de empaquetado alimentando datos de prueba canónicos.
- **AC:** El binario pasa con éxito el `gltf-validator` oficial de Khronos sin errores estructurales.

---

## [ ] Fase 2 — Pipeline B: Renderizado Offline de Video (Blender Headless)

- **Objetivo:** Implementar la secuencia asíncrona de extracción de movimiento de video humano y su renderizado fotorrealista posterior sobre el avatar generado usando scripts de Blender en GPU.
- **AC global de la Fase:** Un Job insertado en `queue:motion` procesa un video `.mp4` y entrega el video renderizado del personaje `.mp4` finalizado en la carpeta de MinIO en menos de 45 segundos.

---

### [ ] Sub Fase 2.1 — Extracción de Movimiento Humano (MS 4.1)

- **Objetivo:** Procesar videos 2D, estimar la pose 3D continua mediante WHAM y exportar la animación a `.bvh`.
- **AC global de la Sub Fase:** Archivo `motion.bvh` estructurado de forma idéntica al armature humanoid estándar de 25 huesos y con datos rotacionales por frame.

#### [ ] T2.1.1 — Worker de Extracción de Pose 3D Continua
- **Objetivo:** Programar el worker de extracción cinemática de video.
- **AC:** Animación BVH continua y limpia.

##### [ ] A2.1.1.1 — Codificación del Worker WHAM (Python)
- **Objetivo:** Escribir la inferencia de WHAM/SMPL en Python.
- **Input:** Archivo de video `.mp4` / `.webm` cargado en MinIO.
- **Output:** Módulo `services/video_render/ms_motion_extract/worker.py`.
- **Proceso:**
  - Decodificar los frames de video a 30 FPS constantes.
  - Ejecutar YOLOv8-Pose para detectar el actor y estimar las poses 3D mediante WHAM en GPU.
  - Aplicar filtro de suavizado Savitzky-Golay sobre el flujo rotacional de los joints detectados.
  - Interpolar joints SMPL al esqueleto de 25 huesos humanoid y exportar a `animation/motion.bvh`.
- **Tests:** Inferencia sobre un video de prueba de 5 segundos con levantamiento de brazos.
- **AC:** El archivo `.bvh` resultante contiene los 150 frames continuos y es importable en herramientas de modelado estándar.

---

### [ ] Sub Fase 2.2 — Headless Blender Rendering (MS 4.2)

- **Objetivo:** Integrar el renderizado final 3D por GPU en consola de comandos mediante Docker e interacciones asíncronas de Celery.
- **AC global de la Sub Fase:** Video final renderizado por Eevee y codificado con FFmpeg en la ruta de MinIO.

#### [ ] T2.2.1 — Worker Blender GPU Headless
- **Objetivo:** Escribir el script Python de automatización de Blender (`bpy`) y el contenedor de ejecución.
- **AC:** Renderizado de video MP4 fluido a 30 FPS.

##### [ ] A2.2.1.1 — Script de Retargeting y Renderizado en Blender (`render_script.py`)
- **Objetivo:** Escribir la automatización de la escena 3D y renderizado por script.
- **Input:** Archivo de avatar `.glb` y animación `.bvh`.
- **Output:** Script en Python `services/video_render/ms_headless_render/render_script.py`.
- **Proceso:**
  - Limpiar la escena de Blender por script e importar el `.glb` y `.bvh`.
  - Crear restricciones de copia de rotación (`COPY_ROTATION`) para cada par de huesos correspondientes.
  - Configurar cámara orbital apuntando al personaje, luces de escena y fondo optimizados.
  - Configurar motor de renderizado `Eevee` y codificación de salida FFmpeg H.264 MP4.
  - Ejecutar el render frame a frame de la animación y exportar a `{job_id}/output/final_video.mp4`.
- **Tests:** Ejecutar localmente `blender --background --python render_script.py -- config.json`.
- **AC:** Renderizado finalizado con éxito que entrega un video MP4 fluido con iluminación dinámica.

##### [ ] A2.2.1.2 — Setup del Worker de Blender Headless (Dockerfile)
- **Objetivo:** Construir el contenedor Docker con Blender, soporte de GPU (CUDA) y Celery.
- **Input:** Dockerfile base y scripts.
- **Output:** Dockerfile en `services/video_render/ms_headless_render/Dockerfile`.
- **Proceso:**
  - Utilizar imagen base con CUDA `nvidia/cuda:12.4.0-cudnn9-runtime-ubuntu22.04`.
  - Descargar e instalar Blender Headless, dependencias de Python y FFmpeg.
  - Configurar el worker Celery de Python para escuchar en la cola `queue:render` y ejecutar el renderizado asíncronamente llamando a Blender en consola.
- **Tests:** Ejecutar el contenedor docker integrado en la red local.
- **AC:** El contenedor arranca, detecta la GPU NVIDIA física local e inicializa el socket de Celery.

---

## [ ] Fase 3 — API Gateway Completo, Colas y Almacenamiento S3

- **Objetivo:** Refinar la API de Rust (Axum) para soportar almacenamiento directo de archivos grandes, generación segura de Presigned URLs firmadas, y comunicación robusta con colas Redis y Workers asíncronos.
- **AC global de la Fase:** El Gateway gestiona subidas de archivos en multipart de 100MB, asigna Job IDs únicos en Redis, despacha tareas a Celery y sirve URLs temporales válidas.

---

### [ ] Sub Fase 3.1 — Proxy Multipart y Presigned S3 Client

- **Objetivo:** Servir y optimizar la transmisión binaria de imágenes y videos pesados.
- **AC global de la Sub Fase:** Transmisión robusta libre de bloqueos de sockets y control de memoria óptimo.

#### [ ] T3.1.1 — Cliente S3 y Colas Celery en Rust
- **Objetivo:** Programar la lógica de subida y encolamiento asíncrono en Rust.
- **AC:** Gateway encola tareas y responde con HTTP 202 de forma asíncrona.

##### [ ] A3.1.1.1 — Cliente de S3 y Presigned URLs
- **Objetivo:** Escribir el módulo de Rust de interacción S3.
- **Input:** Credenciales de entorno MinIO.
- **Output:** Módulo `gateway/src/services/minio_client.rs`.
- **Proceso:**
  - Configurar cliente usando el SDK oficial de AWS para Rust (`aws-sdk-s3`).
  - Implementar funciones de subida de archivos y generación de Presigned URLs (`Presigned GET URL`) válidas por 1 hora.
- **Tests:** Test unitario en Rust que genere una URL firmada y verifique su legibilidad vía curl.
- **AC:** La URL firmada permite descargar el recurso binario desde el navegador sin incluir credenciales maestras.

##### [ ] A3.1.1.2 — Productor de Celery y Job Tracker en Redis
- **Objetivo:** Encolar tareas JSON legibles por Celery y gestionar transiciones de estado.
- **Input:** Solicitud de Job en multipart HTTP.
- **Output:** Módulos `redis_queue.rs` y `job_tracker.rs` en Gateway Rust.
- **Proceso:**
  - Al recibir archivo, subir a MinIO $\rightarrow$ generar UUID del Job $\rightarrow$ guardar estado inicial `queued` en Redis (`job:status:{id}`) $\rightarrow$ insertar payload en cola LPUSH compatible con Celery.
- **Tests:** Subir imagen mediante POST REST simulado.
- **AC:** Respuesta HTTP 202 con Job ID válido y registro insertado en Redis verificado con `redis-cli`.

---

## [ ] Fase 4 — Frontend Unificado de Producción y Paneles Reactivos

- **Objetivo:** Integrar la UI completa del monorepo unificando la estética dark "BioRender Punk" con subidas multipart en React, barras de progreso reactivas que consumen estados asíncronos del Gateway y visualizadores duales en paralelo.
- **AC global de la Fase:** La interfaz web permite cargar imágenes y videos, muestra barras de progreso reactivas coherentes y despliega de manera armónica el video renderizado junto al avatar tridimensional.

---

### [ ] Sub Fase 4.1 — UI Unificada y Barra de Progreso Reactiva

- **Objetivo:** Construir interfaz rica de alta interacción y polling continuo inteligente.
- **AC global de la Sub Fase:** El usuario experimenta respuestas ágiles de carga y monitorización fluida del estado de las tareas GPU asíncronas.

#### [ ] T4.1.1 — Componentes Reactivos de Subida y Reproducción
- **Objetivo:** Diseñar los cargadores de imagen y video e integrar la reproducción fotorrealista.
- **AC:** Integración interactiva de Astro y React exitosa.

##### [ ] A4.1.1.1 — Componentes multipart (`ImageUploader.tsx` y `VideoUploader.tsx`)
- **Objetivo:** Crear los drag-and-drop y el flujo de polling interactivo.
- **Input:** Estilos BioRender Punk CSS.
- **Output:** Componentes React en `frontend/src/components/react/`.
- **Proceso:**
  - Diseñar interfaz con áreas delimitadas, bordes sólidos rígidos de 2px y textos en IBM Plex Mono.
  - Implementar carga Multipart a los endpoints del Gateway Rust.
  - Implementar polling inteligente de estado cada 3 segundos (`GET /api/jobs/{id}`) que actualice barras de progreso en porcentaje.
- **Tests:** Cargar e interactuar con subidas de archivos en el navegador local.
- **AC:** Progreso visual en pantalla que refleja fielmente las transiciones del estado del job (`queued` $\rightarrow$ `processing` $\rightarrow$ `done`).

##### [ ] A4.1.1.2 — Integración Doble de Reproductor y Visor 3D (`VideoPlayer.tsx` y unificación)
- **Objetivo:** Crear el visor dual en paralelo.
- **Input:** Layout general Astro.
- **Output:** Componente e integración en `frontend/src/pages/index.astro`.
- **Proceso:**
  - Maquetar grid de dos columnas: izquierda para el visor WebGL de R3F (`Viewer3D`) cargando el avatar final, y derecha para el reproductor HTML5 (`VideoPlayer`) reproduciendo el video renderizado desde la URL temporal S3.
- **Tests:** Visualizar flujo completo en el navegador Chrome/Firefox.
- **AC:** Ambos visores conviven e interactúan fluidamente a alta resolución sin interferencias o caídas de framerate.
