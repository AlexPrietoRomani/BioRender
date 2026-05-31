# Arquitectura del Sistema - BioRender

> **Audiencia:** Arquitectos de solución, líderes técnicos, desarrolladores y gerentes de TI.
> **Alcance:** Describe la estructura fundamental del sistema **BioRender**, detallando la interconexión de alto nivel entre componentes, los flujos asíncronos y en tiempo real, el modelo de datos físico, y la topología de red y despliegue sobre contenedores con aceleración por hardware.

---

## 1. Visión General del Sistema (C4 – Nivel Contexto)

El sistema **BioRender** permite a los usuarios interactuar con avatares 3D generados a partir de imágenes, capturar sus movimientos físicos y ver animaciones automáticas tanto en vivo como en diferido.

```mermaid
flowchart TB
    subgraph Actores["Actores Principales"]
        U_Final["👤 Usuario Final / Actor\n(Usa la cámara y sube archivos)"]
        U_Admin["👤 Administrador / Operador\n(Configura modelos y monitoriza jobs)"]
    end

    subgraph Sistema["Sistema Central BioRender"]
        direction TB
        APP["BioRender Platform\n─────────────────\nOrquesta la generación 3D, extracción de movimiento y visualización en tiempo real."]
    end

    subgraph Sistemas_Externos["Dependencias y Almacenamiento"]
        S3_Bucket[("Object Storage MinIO\n─────────────\nPersistencia de GLB, BVH y MP4")]
        Redis_Broker[("Redis Broker & Cache\n─────────────\nColas Celery y estados efímeros")]
    end

    U_Final -->|Usa interfaz web y transmite frames| APP
    U_Admin -->|Administra recursos del sistema| APP
    APP <-->|Subidas/Descargas con URLs firmadas| S3_Bucket
    APP <-->|Encola tareas y lee estados| Redis_Broker
```

### Decisiones arquitectónicas clave (Nivel Macro):
*   **Enfoque de Microservicios Desacoplados:** Cada componente de procesamiento computacional pesado corre en su propio contenedor optimizado para GPU, evitando interferir con el Gateway HTTP del sistema.
*   **Comunicación Híbrida:** Uso de HTTP REST clásico para flujos transaccionales y subida de archivos; WebSockets bidireccionales asíncronos para streaming de baja latencia; y arquitectura dirigida por eventos (LPUSH/RPOP) mediante Redis/Celery para tareas GPU en segundo plano.

---

## 2. Componentes Internos (C4 – Nivel Contenedor)

Desglose de la arquitectura de BioRender en sus aplicaciones y capas físicas independientes:

```mermaid
flowchart TB
    subgraph Cliente["Capa de Presentación (Navegador)"]
        UI_Astro["Astro Web App\n(Layouts y Páginas)"]
        Viewer_3D["Visor R3F (React)\n(WebGL Canvas)"]
        LiveCamera["Live Camera (React)\n(WebRTC + Canvas Extractor)"]
        VideoUploader["Uploader Components\n(Subida e interfaz reactiva)"]
        
        UI_Astro --> LiveCamera & Viewer_3D & VideoUploader
    end

    subgraph Backend["Capa de Aplicación y Orquestación"]
        API_Gateway["Rust API Gateway\n(Axum Server :8080)"]
        Retarget_Engine["Motor de Retargeting\n(Rust glam local)"]
        WS_Hub["WebSocket Hub\n(Gestor de conexiones RT)"]
        
        API_Gateway --- WS_Hub
        WS_Hub --- Retarget_Engine
    end

    subgraph Colas["Capa de Mensajería y Eventos"]
        Redis[("Redis Broker\n(LPUSH queue:*)")]
    end

    subgraph Workers["Workers de GPU (Python Celery)"]
        direction TB
        W_Multiview["MS 3.1: Zero123++\n(Generación Multi-vista)"]
        W_Reconstruct["MS 3.2: InstantMesh\n(Reconstrucción 3DGS)"]
        W_Rigging["MS 3.3: RigNet\n(Auto-Rigging Grafo)"]
        W_AssetAssembly["MS 3.4: Asset Assembler\n(Rust Crate compilado)"]
        
        W_Motion["MS 4.1: WHAM\n(SMPL a BVH)"]
        W_Blender["MS 4.2: Headless Blender\n(Blender Python Render)"]
    end

    subgraph Inferencia_RT["Pipeline Tiempo Real (Pipeline C)"]
        FastAPI_Pose["MS 5.1: FastAPI Pose\n(MediaPipe / YOLO :8001)"]
    end

    subgraph Datos["Capa de Almacenamiento Binario"]
        Minio[("MinIO Object Storage\n(Compatible API S3 :9000)")]
    end

    %% Conexiones
    LiveCamera -->|wss:// Stream frames JPEG base64| WS_Hub
    WS_Hub -->|bone_rotations JSON| Viewer_3D
    VideoUploader -->|POST /api/generate-3d /api/process-video| API_Gateway
    
    API_Gateway -->|Sube inputs| Minio
    API_Gateway -->|Encola Jobs| Redis
    
    Redis -->|Consumen tareas| W_Multiview & W_Reconstruct & W_Rigging & W_AssetAssembly & W_Motion & W_Blender
    W_Multiview & W_Reconstruct & W_Rigging & W_AssetAssembly & W_Motion & W_Blender <-->|Lecturas/Escrituras binarias| Minio
    
    WS_Hub -->|POST /detect-pose via HTTP| FastAPI_Pose
```

### Flujo de una interacción típica:
1.  **Pipeline Asíncrono (Pipeline A/B):** El navegador sube un archivo $\rightarrow$ El API Gateway (Rust) recibe el binario y lo almacena directamente en MinIO $\rightarrow$ Registra el Job e inserta un evento en Redis $\rightarrow$ El Worker de IA en Celery consume la tarea $\rightarrow$ Procesa el pipeline IA (bajo GPU, o CPU si no hay CUDA activo) $\rightarrow$ Sube los assets finales a MinIO y marca el Job como `done` en Redis.
2.  **Pipeline en Tiempo Real (Pipeline C):** El componente `LiveCamera` captura un stream de cámara web $\rightarrow$ Codifica frames a JPEG Base64 $\rightarrow$ Envía los frames vía WebSocket al Gateway $\rightarrow$ El Gateway delega la detección a `ms_pose_rt` $\rightarrow$ Recibe los keypoints 3D $\rightarrow$ Calcula instantáneamente el retargeting matemático con `RetargetEngine` en Rust $\rightarrow$ Devuelve los cuaterniones al navegador $\rightarrow$ `Viewer3D` rota los huesos del avatar.

> [!NOTE]
> **Bypass de Sandbox de Cámara en Windows**: El diseño del Pipeline C soluciona de raíz la imposibilidad de montar dispositivos USB de cámara físicos (`/dev/video0`) en contenedores Docker corriendo en hosts Windows/WSL2. Al capturar el stream en la Capa de Presentación del cliente, comprimir cada frame y transmitirlo secuencialmente por WebSocket, la infraestructura de contenedores funciona de forma desacoplada y 100% portable.

---

## 3. Flujo de Secuencia (Casos de Uso Complejos)

### 3.1 Flujo de Inferencia y Retargeting en Tiempo Real (Pipeline C)
Este flujo exige una latencia mínima e integra la cámara web, el API Gateway de Rust, el servidor de inferencia Python MediaPipe y el visor en tres dimensiones:

```mermaid
sequenceDiagram
    autonumber
    actor User as Actor / Usuario
    participant CAM as Cámara (WebRTC)
    participant FE as Componente LiveCamera
    participant GW as Gateway WS Hub (Rust)
    participant PD as MS 5.1 Pose Server (FastAPI)
    participant RT as RetargetEngine (Rust Local)
    participant V3D as Visor R3F (WebGL)

    User->>CAM: Otorga permisos de captura
    CAM->>FE: Stream continuo de video (HTMLVideoElement)
    
    loop Cada frame (~33ms a 30 FPS)
        FE->>FE: Renderiza en Canvas oculto
        FE->>FE: canvas.toBlob() (JPEG comprimido Base64)
        FE->>GW: WS: FrameMessage { type: "frame", data: base64 }
        GW->>PD: POST /detect-pose { frame_data: base64 }
        Note over PD: Inferencia MediaPipe / YOLO<br/>(Detección Landmarks en CPU/GPU)
        PD-->>GW: JSON: { keypoints: [...], confidence }
        GW->>RT: retarget_engine.compute(keypoints)
        Note over RT: Convierte keypoints a cuaterniones<br/>(Rest Pose → Target Direction)
        RT-->>GW: bone_rotations: [{ bone_name, quaternion }]
        GW-->>FE: WS: PoseResultMessage { type: "pose_result", bone_rotations }
        FE->>V3D: Emite rotaciones de huesos al armature
        Note over V3D: bone.quaternion.set(quat)<br/>WebGL renderiza nuevo estado
    end
```

---

## 4. Modelo de Dominio / Entidad-Relación

BioRender opera de forma asíncrona mediante el concepto de **Jobs** y almacena estructuras jerárquicas binarias en MinIO asociadas con identificadores persistidos de forma efímera en Redis.

```mermaid
flowchart TD
    subgraph Dominio_de_Jobs["Estados y Flujo de Trabajo"]
        JOB["Job (Trabajo Asíncrono)\n─────────────────\njob_id (UUID)\ntype (generation_3d / video_process)\nstatus (queued / processing / done / error)\nprogress (0-100)\ncreated_at (timestamp)\nupdated_at (timestamp)\nresult_url (string)\nerror_message (string)"]
    end

    subgraph Almacenamiento_Fisico_S3["Estructura de Objetos (MinIO)"]
        INPUT_BIN["uploads/{job_id}/input.png (Imagen)\nuploads/{job_id}/input_video.mp4 (Video)"]
        MULTIVIEW_BIN["uploads/{job_id}/multiview/view_*.png (6 Vistas)"]
        GEOMETRY_BIN["uploads/{job_id}/mesh/model.obj + texture.png"]
        RIG_BIN["uploads/{job_id}/rigged/model_rigged.fbx + skeleton.json"]
        GLB_BIN["uploads/{job_id}/final/avatar.glb (Asset 3D Final)"]
        ANIM_BIN["uploads/{job_id}/animation/motion.bvh (Animación)"]
        RENDER_BIN["uploads/{job_id}/output/final_video.mp4 (Video Final)"]
    end

    JOB -->|1:1 Input| INPUT_BIN
    JOB -->|1:N Vistas| MULTIVIEW_BIN
    JOB -->|1:1 Reconstrucción| GEOMETRY_BIN
    JOB -->|1:1 Huesos| RIG_BIN
    JOB -->|1:1 GLB Generado| GLB_BIN
    JOB -->|1:1 Animación Extraída| ANIM_BIN
    JOB -->|1:1 Video Renderizado| RENDER_BIN
```

---

## 5. Arquitectura de Despliegue (Infraestructura)

El despliegue de BioRender utiliza contenedores Docker organizados localmente por `docker-compose` con soporte dinámico de GPU (vía `nvidia-container-toolkit`) y fallback completo a CPU. Esto garantiza la ejecución portable sin comprometer el rendimiento en servidores con aceleración por hardware:

```mermaid
flowchart LR
    subgraph Host_Desarrollo["Entorno Local (Docker Desktop / Localhost)"]
        direction TB
        
        FE_Astro["Astro Front-End\n(:4321)"]
        Rust_Gateway["Axum Gateway Router\n(:8080)"]
        
        subgraph Docker_Infra["Infraestructura de Soporte Docker"]
            Redis_Svc["Redis Broker\n(:6379)"]
            Minio_Svc["MinIO API\n(:9000)\nMinIO Console\n(:9001)"]
        end
        
        subgraph Docker_IA_Hibrido["Workers de IA e Inferencia (Híbrido CPU / GPU NVIDIA)"]
            FastAPI_PoseRT["Pose Inferencia RT\n(ms_pose_rt :8001)\n[CPU / GPU Fallback]"]
            Celery_Workers["Celery GPU Workers\n(Zero123, InstantMesh, WHAM)\n[Autodetección CUDA o CPU Hilos]"]
            Blender_Headless["Blender Headless Worker\n(Blender Engine Eevee CPU/GPU)"]
        end
    end

    %% Conexiones de flujo locales
    FE_Astro <-->|API HTTP / WebSockets| Rust_Gateway
    Rust_Gateway <-->|Encola tareas| Redis_Svc
    Rust_Gateway <-->|Persistencia| Minio_Svc
    Rust_Gateway -->|POST landmarks| FastAPI_PoseRT
    
    Celery_Workers & Blender_Headless <-->|RPOP / LPUSH| Redis_Svc
    Celery_Workers & Blender_Headless <-->|Lee/Escribe archivos| Minio_Svc
```

> [!TIP]
> **Optimización de Recursos**: Todos los contenedores de esta topología tienen límites rígidos de memoria (`limits.memory`) configurados en el compose file. Esto garantiza que las cargas concurrentes no desestabilicen el sistema operativo Windows anfitrión y mitiga las fugas de memoria OOM en el backend.

---

## 6. Decisiones Arquitectónicas Relevantes (ADRs Resumidos)

| Decisión Tomada | Alternativas Descartadas | Razón Principal e Histórica |
| :--- | :--- | :--- |
| **Inferencia RT con MediaPipe en CPU (Prototipo MVP)** | YOLOv8-Pose TensorRT, RTMPose | Permite desarrollar, simular y validar el MVP de inmediato en cualquier hardware local sin obligar a la pre-configuración de drivers NVIDIA y librerías CUDA complejas desde la primera fase. |
| **Orquestador Asíncrono de Colas en Redis (Celery)** | RabbitMQ, Apache Kafka | Python cuenta con una integración inmejorable con Celery sobre Redis. Minimiza la fricción de desarrollo al utilizar exactamente las mismas clases de negocio de inferencia profunda. |
| **Retargeting Matemático de Huesos en el Gateway (Rust)** | Calcular retargeting en el Navegador (JavaScript) | Aliviar la carga computacional del dispositivo del cliente (móviles o portátiles de gama media). Rust con la librería `glam` realiza los cálculos vectoriales en $< 0.1ms$ por frame antes de despachar. |
| **Almacenamiento compatible S3 local (MinIO)** | Almacenamiento local en disco rígido montado en carpetas | El uso de la API S3 mediante MinIO garantiza que el sistema sea cloud-native. Migrar a AWS S3 en producción requiere únicamente la edición de variables de entorno del archivo `.env`, sin modificar código. |
| **Ingress Bypass de Cámara por WebSocket (Frontend-Proxy)** | Montaje directo de `/dev/video0` en Docker | Resuelve la restricción técnica de sandboxing de dispositivos USB del host Windows/WSL2 en Docker Desktop de forma nativa e independiente de la plataforma host, logrando máxima portabilidad. |
| **Estrategia Híbrida de Inferencia (CPU/GPU Fallback)** | Contenedores separados exclusivos por hardware | Evita la duplicación y mantenimiento de imágenes Docker diferentes. El microservicio en runtime detecta CUDA (`torch.cuda.is_available()`) y ajusta la complejidad de los pesos y multihilos. |
