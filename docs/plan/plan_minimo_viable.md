# BioRender - Plan de Implementación Mínimo Viable (MVP)

> **Propósito.** Este documento define la ruta de ejecución y especificación técnica para construir el Mínimo Viable (MVP) de **BioRender**. El MVP tiene como objetivo único capturar la transmisión de la cámara web del usuario en tiempo real, detectar sus movimientos corporales y aplicar dicha animación de forma instantánea ("retargeting") sobre un modelo 3D estático básico (personaje dummy) renderizado en el navegador.
>
> **Persistencia:** No se requiere base de datos persistente (SQL/NoSQL) ni almacenamiento de objetos (S3/MinIO) para el MVP, operando de forma puramente transitoria en memoria/WebSockets para minimizar la complejidad.
>
> **Tooling:** Frontend (Astro 5.x + React 19 + R3F + npm), Gateway (Rust + Axum + Tokio), Microservicio de Pose (Python 3.10 + FastAPI + MediaPipe + pip).

---

## Índice

1. [Convenciones y Nomenclatura](#1-convenciones-y-nomenclatura)
2. [Stack Tecnológico Definitivo (MVP)](#2-stack-tecnologico-definitivo-mvp)
3. [Estructura Objetivo del Repositorio (MVP)](#3-estructura-objetivo-del-repositorio-mvp)
4. [Datos de Referencia (Fixtures)](#4-datos-de-referencia-fixtures)
5. **Fase 0** — [Setup, Tooling e Infraestructura Base](#fase-0--setup-tooling-e-infraestructura-base)
6. **Fase 1** — [Modelado de Dominio, Protocolo y Tipos](#fase-1--modelado-de-dominio-protocolo-y-tipos)
7. **Fase 2** — [Microservicio de Detección de Pose RT](#fase-2--microservicio-de-deteccion-de-pose-rt)
8. **Fase 3** — [API Gateway y WebSocket Hub](#fase-3--api-gateway-y-websocket-hub)
9. **Fase 4** — [Visualizador 3D y Captura en Frontend](#fase-4--visualizador-3d-y-captura-en-frontend)
10. **Fase 5** — [Integración, Testing y Criterios de Aceptación](#fase-5--integracion-testing-y-criterios-de-aceptacion)
11. [Apéndices](#apendices)

---

## 1. Convenciones y Nomenclatura

Para evitar ambigüedades semánticas en este MVP, adoptamos las siguientes reglas:

- **Terminología de Negocio:**
  - **Actor / Usuario:** La persona frente a la cámara cuyo movimiento es capturado.
  - **Avatar Dummy / Personaje:** El modelo 3D base (.glb) con esqueleto estándar humanoid sobre el cual se superpone el movimiento.
  - **Frame:** Imagen estática (JPEG) extraída secuencialmente de la cámara a 30 FPS.
  - **Keypoint:** Coordenada espacial 3D $(x, y, z)$ estimada para una articulación específica del cuerpo humano.
  - **Bone Rotation:** El cuaternión resultante $(x, y, z, w)$ para rotar un hueso del modelo 3D a partir de los keypoints.
- **Identificadores y Código:**
  - `snake_case` para variables y funciones en Python y Rust.
  - `camelCase` para variables, propiedades y funciones en TypeScript/React.
  - `PascalCase` para componentes React y structs de Rust.
- **Reglas Arquitectónicas de Diseño:**
  - **Baja Latencia Obligatoria:** El flujo del frame desde la cámara web hasta el renderizado de la rotación del hueso en el navegador debe completarse en $< 50ms$ en red local.
  - **Sin Estado (Stateless):** El API Gateway y el microservicio de detección de pose no guardarán logs de imágenes ni archivos en disco. El estado de la pose se consume en tiempo real y se desecha inmediatamente.

---

## 2. Stack Tecnológico Definitivo (MVP)

A continuación se detalla la matriz de tecnologías rigurosamente justificadas para el MVP:

| Capa / Dominio | Tecnología Preferida | Versión Sugerida | Justificación / Notas Técnicas |
| :--- | :--- | :--- | :--- |
| **Lenguaje Backend (Gateway)** | Rust | 1.78+ | Rendimiento, concurrencia segura y procesamiento matemático rápido (nalgebra/glam). |
| **Framework HTTP / WS (Gateway)** | Axum | 0.7+ | Framework asíncrono robusto construido sobre Tokio, óptimo para WebSockets concurrentes. |
| **Lenguaje Backend (IA)** | Python | 3.10 | Requerido por la madurez y compatibilidad nativa del ecosistema de MediaPipe y OpenCV. |
| **Framework API (IA)** | FastAPI | 0.110+ | Framework web ultrarrápido y asíncrono con tipado estático nativo y auto-documentación OpenAPI. |
| **Motor de Inferencia de Pose** | MediaPipe Pose | 0.10.x | Excelente rendimiento de inferencia en CPU (5-8ms), eliminando la necesidad obligatoria de GPUs dedicadas en local. |
| **Framework Frontend / UI** | Astro | 5.x | Generación estática súper veloz combinada con islas interactivas React para la visualización en 3D. |
| **Librería de Componentes UI** | React | 19.x | Hidratación interactiva flexible para gestionar el estado de los streams y controles del visualizador. |
| **Visualización 3D** | React Three Fiber (R3F) | 9.x | Envoltura declarativa para Three.js que simplifica el renderizado de la escena WebGL y la manipulación de huesos. |
| **Estilos / Diseño** | Vanilla CSS | CSS3 | Máxima flexibilidad, rendimiento óptimo y control del diseño "BioRender Punk" sin abstracciones pesadas. |
| **Testing Suite** | pytest + Jest | - | Pruebas unitarias matemáticas para el cálculo de cuaterniones (Rust) y de inferencia (Python). |

---

## 3. Estructura Objetivo del Repositorio (MVP)

Representación del monorepo simplificado para el MVP:

```text
BioRender/
│
├── docker-compose.yml             # Orquestación del MVP (Gateway + Pose RT)
├── .env.example                   # Variables del entorno (puertos, endpoints)
├── .gitignore
│
├── frontend/                      # Capa 1: UI Astro + React
│   ├── package.json
│   ├── astro.config.mjs
│   ├── src/
│   │   ├── layouts/
│   │   │   └── Layout.astro       # Layout general "BioRender Punk"
│   │   ├── pages/
│   │   │   └── index.astro        # Landing page del MVP
│   │   ├── components/
│   │   │   ├── react/
│   │   │   │   ├── LiveCamera.tsx # Captura WebRTC + WebSocket
│   │   │   │   └── Viewer3D.tsx   # Visor WebGL / Canvas R3F
│   │   │   └── astro/
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts    # Conector bidireccional RT
│   │   └── styles/
│   │       └── global.css         # CSS BioRender Punk (Dark-first)
│   └── public/
│       └── models/
│           └── dummy_humanoid.glb # Personaje humanoid por defecto
│
├── gateway/                       # Capa 2: Rust API Gateway
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs                # Inicializador de Axum Router
│       ├── routes/
│       │   ├── ws_live.rs         # Enrutador WebSocket y proxy de pose
│       │   └── mod.rs
│       └── retargeting/
│           ├── mod.rs             # Motor matemático de retargeting
│           └── math.rs            # Operaciones con glam::Quat y glam::Vec3
│
└── services/
    └── realtime/
        └── ms_pose_rt/            # Capa 3: Microservicio de Inferencia
            ├── Dockerfile
            ├── requirements.txt
            └── main.rs / main.py  # FastAPI + MediaPipe Pose
```

---

## 4. Datos de Referencia (Fixtures)

Establecemos la verdad matemática fundamental del MVP para garantizar pruebas unitarias fiables.

### Escenario / Inputs Canónicos (Pose 2D/3D Landmarks):
MediaPipe Pose retorna 33 landmarks con coordenadas $(x, y, z)$ normalizadas en relación con el volumen de captura.
Para pruebas matemáticas del motor de retargeting, usaremos los siguientes keypoints simplificados correspondientes al brazo izquierdo extendido horizontalmente:

| Landmark (MediaPipe Index) | Keypoint Name | Coordenadas Canónicas $(x, y, z)$ |
| :--- | :--- | :--- |
| **11** | `left_shoulder` | $(0.0, 0.0, 0.0)$ |
| **13** | `left_elbow` | $(-0.3, 0.0, 0.0)$ |
| **15** | `left_wrist` | $(-0.6, 0.0, 0.0)$ |

### Salidas Esperadas (Golden Data - Rotación de Huesos):
Para la posición anterior (brazo perfectamente extendido hacia la izquierda del actor), el vector de dirección medido de hombro a codo es $V_{dir} = (-1.0, 0.0, 0.0)$.
Considerando que la "Rest Pose" del modelo 3D (T-Pose) tiene el brazo izquierdo alineado al eje $-X$ global, el cuaternión de rotación calculado para el hueso `LeftArm` debe ser cercano a la identidad:

*   **Hueso `LeftArm`:** $Q_{world} = [0.0, 0.0, 0.0, 1.0]$ (sin rotación respecto al eje de descanso).

Si el actor levanta el brazo codo arriba a $90^\circ$, el vector de dirección es $V_{dir} = (0.0, 1.0, 0.0)$. El cuaternión de rotación debe mapear la rotación de $90^\circ$ sobre el eje Z:

*   **Hueso `LeftArm`:** $Q_{world} = [0.0, 0.0, 0.7071, 0.7071]$ (rotación de $90^\circ$ en Z).

---

## 5. Fases de Ejecución

### Fase 0 — Setup, Tooling e Infraestructura Base

**Macro-objetivo:** Inicializar las tres estructuras de código (Astro, Rust, Python), configurar herramientas de linting y formateo, y levantar la infraestructura local simulada mediante Docker Compose.

#### Sub Fase 0.1 — Configuración del Repositorio y Tooling
*   **Micro-objetivo:** Inicializar manifiestos de dependencias (`package.json`, `Cargo.toml`, `requirements.txt`).
*   **AC:** Comandos de instalación terminan con código 0.

##### T0.1.1 — Inicialización de Estructuras Locales
- **Entregable:** Proyectos compilables e instalables de manera aislada.
- **Acciones:**
  - Inicializar proyecto Astro con `npm create astro@latest ./frontend -- --no-install`.
  - Crear proyecto Rust con `cargo new ./gateway --bin`.
  - Configurar entorno virtual de Python en `./services/realtime/ms_pose_rt`.
- **AC:** `npm install`, `cargo check` y `pip install -r requirements.txt` se completan sin errores en sus respectivos directorios.

##### T0.1.2 — Setup de Orquestación Docker Compose
- **Entregable:** Archivo `docker-compose.yml` para el despliegue integrado del MVP local.
- **Acciones:**
  - Crear archivo `docker-compose.yml` que orqueste la ejecución de `gateway` y `pose-rt`.
  - Configurar puertos de escucha locales: `8080` (Gateway) y `8001` (Pose RT).
- **AC:** `docker-compose up --build` arranca los contenedores e imprimen sus health checks correspondientes.

---

### Fase 1 — Modelado de Dominio, Protocolo y Tipos

**Macro-objetivo:** Diseñar y codificar las estructuras de datos inmutables y los payloads de WebSocket para la comunicación entre el navegador, el Gateway de Rust y el microservicio de inferencia de Python.

#### Sub Fase 1.1 — Definición del Protocolo de WebSocket
*   **Micro-objetivo:** Establecer esquemas de serialización JSON libres de acoplamiento.
*   **AC:** Validación de tipo estricta sin errores en TypeScript, Rust y Python.

##### T1.1.1 — Contratos de Transmisión (WS Payloads)
- **Entregable:** Definición de tipos de mensajería bidireccional.
- **Acciones:**
  - **Frame Message (Cliente → Gateway):** Payload que transporta el frame de cámara codificado en Base64 JPEG.
  - **Pose Result Message (Gateway → Cliente):** Payload que entrega el arreglo de rotaciones de huesos calculadas.
- **AC:** Los esquemas serializados son totalmente validados en el Gateway mediante `serde` y en el frontend con TypeScript.

##### T1.1.2 — Modelos de Keypoints e Inferencia
- **Entregable:** Estructuras internas para representar los puntos clave de pose de MediaPipe.
- **Acciones:**
  - Definir DTOs para `Keypoint` con coordenadas $(x, y, z)$ y nivel de `visibility` (confianza de detección).
- **AC:** Pruebas de deserialización exitosas a partir de outputs JSON simulados de MediaPipe.

---

### Fase 2 — Microservicio de Detección de Pose RT

**Macro-objetivo:** Desarrollar el microservicio independiente en Python que capture los frames de imagen Base64 del Gateway y ejecute inferencia ultrarrápida usando MediaPipe Pose, retornando los landmarks detectados.

#### Sub Fase 2.1 — API de Inferencia MediaPipe con FastAPI
*   **Micro-objetivo:** Inferencia de landmarks humanos en CPU a menos de 10ms.
*   **AC:** Endpoint `/detect-pose` responde con landmarks y confianza de detección de forma consistente.

##### T2.1.1 — Integración de Inferencia MediaPipe
- **Entregable:** Módulo Python `pose_detector.py` que envuelve el pipeline de MediaPipe.
- **Acciones:**
  - Configurar MediaPipe Pose en modo no estático (`static_image_mode=False`) y baja complejidad (`model_complexity=0` o `1` para priorizar CPU).
  - Implementar decodificador de Base64 a imagen OpenCV en memoria.
- **AC:** Llamadas locales con frames de prueba devuelven un arreglo de 13 landmarks clave mapeados en $< 8ms$.

##### T2.1.2 — Endpoint FastAPI
- **Entregable:** Servidor web asíncrono con endpoint `/detect-pose` expuesto internamente.
- **Acciones:**
  - Crear endpoint `POST /detect-pose` que valide el payload JSON usando Pydantic v2.
  - Añadir health check `/health` para monitorización de estado.
- **AC:** Herramienta de pruebas de API (HTTPie/curl) realiza peticiones simuladas y obtiene un JSON con código de estado 200.

---

### Fase 3 — API Gateway y WebSocket Hub

**Macro-objetivo:** Construir el API Gateway centralizado en Rust que actúe como el orquestador principal, administre la conexión persistente por WebSocket con el navegador, delegue la detección al microservicio de Python y ejecute los cálculos de retargeting matemático de forma local.

#### Sub Fase 3.1 — WebSocket Hub con Axum
*   **Micro-objetivo:** Gestionar flujos bidireccionales concurrentes de WebSockets de forma asíncrona.
*   **AC:** El navegador puede conectarse a `ws://localhost:8080/ws/live-pose` y transmitir datos de frames.

##### T3.1.1 — Servidor WebSocket en Axum
- **Entregable:** Endpoint `/ws/live-pose` manejado de manera asíncrona mediante Axum.
- **Acciones:**
  - Implementar handshake e inicialización del canal WebSocket.
  - Implementar bucle de lectura de mensajes de texto en formato JSON.
- **AC:** Conexiones concurrentes simuladas se abren y cierran de forma segura sin fugas de memoria o bloqueos.

#### Sub Fase 3.2 — Motor Matemático de Retargeting (Rust)
*   **Micro-objetivo:** Convertir coordenadas de keypoints en cuaterniones para los huesos del esqueleto humanoid en menos de 2ms.
*   **AC:** Cálculos de rotación de huesos coinciden exactamente con la "Golden Data" física de referencia.

##### T3.2.1 — Implementación del Algoritmo Cinemático
- **Entregable:** Módulo `gateway/src/retargeting/math.rs` con librerías matemáticas `glam` de Rust.
- **Acciones:**
  - Calcular la dirección del vector hueso: $V_{dir} = P_{hijo} - P_{padre}$ (normalizado).
  - Calcular la rotación entre el vector de rest pose y la dirección medida usando `Quat::from_rotation_arc`.
  - Transformar a rotaciones locales encadenando multiplicaciones de cuaterniones inversos.
- **AC:** Pruebas unitarias confirman que el brazo izquierdo extendido horizontalmente retorna un cuaternión de identidad.

##### T3.2.2 — Orquestación Interna del WS Hub
- **Entregable:** Integración asíncrona que encadena el flujo de datos del frame.
- **Acciones:**
  - Recibir frame por WS $\rightarrow$ Enviar a `/detect-pose` de FastAPI vía HTTP async $\rightarrow$ Calcular retargeting $\rightarrow$ Responder al cliente por WS.
- **AC:** Flujo de datos completo finaliza en $< 25ms$ en pruebas internas de latencia del Gateway.

---

### Fase 4 — Visualizador 3D y Captura en Frontend

**Macro-objetivo:** Construir la interfaz de usuario "BioRender Punk" interactiva en Astro/React que capture la cámara del usuario usando WebRTC, transmita los frames por WebSockets y anime un personaje 3D en tiempo real a través de React Three Fiber.

#### Sub Fase 4.1 — Interfaz Visual y Captura WebRTC
*   **Micro-objetivo:** Captura de video local de baja latencia con renderizado de cámara en vivo en un canvas.
*   **AC:** Transmisión de frames codificados a 30 FPS constantes sobre la conexión WebSocket activa.

##### T4.1.1 — Captura de Cámara en Vivo (`LiveCamera.tsx`)
- **Entregable:** Componente React interactivo que gestiona el stream de video de la cámara web.
- **Acciones:**
  - Utilizar `navigator.mediaDevices.getUserMedia` para inicializar el stream (640x480 o similar para baja latencia).
  - Implementar renderizado oculto en un Canvas HTML5 a intervalos regulares (33ms) para extraer frames JPEG de calidad media (0.6) y codificarlos en Base64.
- **AC:** El componente extrae y transmite los frames al Hook de WebSocket a la tasa de refresco objetivo.

##### T4.1.2 — Conexión WebSocket Hub (`useWebSocket.ts`)
- **Entregable:** Hook React personalizado para el manejo del ciclo de vida del canal bidireccional.
- **Acciones:**
  - Implementar reconexión automática en caso de caída del servidor.
  - Deserializar las respuestas `bone_rotations` recibidas y emitir actualizaciones de estado reactivas al visualizador.
- **AC:** El hook se conecta exitosamente y reporta cambios de estado de pose fluidos en tiempo real.

#### Sub Fase 4.2 — Visualización 3D en Tiempo Real (`Viewer3D.tsx`)
*   **Micro-objetivo:** Renderizado WebGL interactivo en tiempo real utilizando un modelo humanoid GLB.
*   **AC:** El esqueleto del modelo 3D responde inmediatamente a los cuaterniones aplicados a nivel de hueso.

##### T4.2.1 — Carga de Modelo y Mapeo de Huesos
- **Entregable:** Escena WebGL con el modelo `dummy_humanoid.glb` inicializado.
- **Acciones:**
  - Usar R3F y `@react-three/drei` con `useGLTF` para cargar el personaje.
  - Recorrer el esqueleto (armature) del modelo cargado en tiempo de montaje para indexar todos los huesos (`isBone`) en un mapa optimizado en memoria (`useRef`).
- **AC:** El modelo dummy se visualiza correctamente en T-Pose con texturas básicas y luces por defecto.

##### T4.2.2 — Animación de Esqueleto RT
- **Entregable:** Aplicación reactiva de cuaterniones sobre los huesos indexados.
- **Acciones:**
  - Al recibir un nuevo arreglo `bone_rotations` desde el WebSocket, buscar el hueso correspondiente en el mapa y aplicar la rotación: `bone.quaternion.set(x, y, z, w)`.
- **AC:** El modelo 3D reacciona fluidamente a los movimientos de los brazos y tronco del usuario capturados por la cámara web.

---

### Fase 5 — Integración, Testing y Criterios de Aceptación

**Macro-objetivo:** Ejecutar pruebas cruzadas de integración final sobre todo el flujo del MVP, garantizando una latencia de transmisión excelente y la consistencia visual del personaje.

#### Sub Fase 5.1 — Integración E2E Local
*   **Micro-objetivo:** El sistema completo se despliega en local con un solo comando y funciona al instante sin intervenciones manuales complejas.
*   **AC:** El usuario abre el navegador, otorga permisos de cámara web y ve al personaje imitando sus movimientos.

##### T5.1.1 — Pruebas de Latencia y Estabilidad E2E
- **Entregable:** Sistema integrado corriendo de principio a fin.
- **Acciones:**
  - Levantar stack mediante `docker-compose up --build`.
  - Iniciar el servidor local del frontend Astro y acceder a `http://localhost:4321`.
  - Medir la latencia total del flujo de datos (ida y vuelta del frame).
- **AC:** El retargeting se completa de forma continua a un mínimo de 24 FPS reales y una latencia total percibida $< 60ms$.

---

## 6. Apéndices

### Apéndice A — Matriz de Trazabilidad del MVP

| Requerimiento de Negocio (MVP) | Fases / Tareas de Implementación |
| :--- | :--- |
| **Capturar imagen / cámara** | Fase 4 - Sub Fase 4.1 (T4.1.1, T4.1.2) |
| **Detección de movimientos** | Fase 2 - Sub Fase 2.1 (T2.1.1, T2.1.2) |
| **Capa de personaje (Retargeting)** | Fase 3 - Sub Fase 3.2 (T3.2.1, T3.2.2) y Fase 4 - Sub Fase 4.2 (T4.2.1, T4.2.2) |
| **Integración Front & Back Mínimo** | Fase 0 (T0.1.1, T0.1.2) y Fase 5 (T5.1.1) |

### Apéndice B — Definición Global de "Done" (DoD) para el MVP
1.  **Cero dependencias pesadas**: Ningún servicio asíncrono o de persistencia (Redis, Celery, MinIO, bases de datos) está activo o es requerido para inicializar el MVP.
2.  **Linters e Inferencia estricta**: Los tipos en TypeScript de React y el tipado Pydantic en Python pasan todas las validaciones sin directivas `@ts-ignore` ni `Any` injustificados.
3.  **Matemáticas Cubiertas**: Se incluyen al menos 3 casos de prueba unitaria en Rust para el cálculo de cuaterniones a partir de keypoints de entrada.
4.  **Estilo Puro**: La interfaz visual adopta puramente la estética "BioRender Punk" (escala de grises, bordes rígidos y tipografías IBM Plex Mono y Press Start 2P) detallada en los documentos de diseño.
5.  **Despliegue Simple**: Se cuenta con un archivo `docker-compose.yml` que empaqueta y configura los entornos locales listos para ejecutar.
