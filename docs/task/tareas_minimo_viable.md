# Listado de Tareas - BioRender Mínimo Viable (MVP)

> **Fuentes de contexto obligatorias:**
> - Plan de Mínimo Viable: [`docs/plan/plan_minimo_viable.md`](../plan/plan_minimo_viable.md)
> - Diagramas de Arquitectura: [`docs/architecture/arquitectura_biorender.md`](../architecture/arquitectura_biorender.md)
>
> **Convenciones de ID:**
> - **Fase:** `F{n}` — ej. `F0` (Setup e Infraestructura)
> - **Sub Fase:** `SF{f}.{s}` — ej. `SF0.1`
> - **Tarea:** `T{f}.{s}.{t}` — ej. `T0.1.1`
> - **Acción:** `A{f}.{s}.{t}.{a}` — ej. `A0.1.1.1`

---

## Índice

- [Fase 0 — Setup e Infraestructura Base del MVP](#fase-0--setup-e-infraestructura-base-del-mvp)
- [Fase 1 — Protocolo de Comunicación y Modelado de Datos](#fase-1--protocolo-de-comunicacion-y-modelado-de-datos)
- [Fase 2 — Microservicio de Inferencia de Pose en Tiempo Real](#fase-2--microservicio-de-inferencia-de-pose-en-tiempo-real)
- [Fase 3 — API Gateway y Motor de Retargeting en Rust](#fase-3--api-gateway-y-motor-de-retargeting-en-rust)
- [Fase 4 — Interfaz de Usuario y Animación WebGL (Astro + R3F)](#fase-4--interfaz-de-usuario-y-animacion-webgl-astro--r3f)
- [Fase 5 — Integración de Flujo Completo, Pruebas y Aceptación](#fase-5--integracion-de-flujo-completo-pruebas-y-aceptacion)

---

## [X] Fase 0 — Setup e Infraestructura Base del MVP

- **Objetivo:** Inicializar las tres capas del monorepo simplificado del MVP (Frontend Astro, Gateway Rust, Pose RT Python) y orquestar su ejecución conjunta local mediante contenedores.
- **AC global de la Fase:**
  - El comando integrado de empaquetado levanta los tres servicios.
  - No existen colisiones de puertos en local (`4321` Astro, `8080` Gateway Rust, `8001` FastAPI).

---

## [X] Sub Fase 0.1 — Estructura del Monorepo y Docker Setup

- **Objetivo:** Organizar las subcarpetas del proyecto base y escribir los manifiestos de contenedores.
- **AC global de la Sub Fase:** `docker-compose up` levanta el API Gateway y el microservicio de inferencia de manera exitosa y comunicada.

### [X] T0.1.1 — Scaffold del Monorepo
- **Objetivo:** Crear los directorios físicos y archivos base para los tres servicios independientes.
- **AC:** Las tres carpetas (`frontend/`, `gateway/`, `services/realtime/ms_pose_rt/`) son autocompilables e independientes.

#### [X] A0.1.1.1 — Scaffold del Frontend (Astro 5.x)
- **Objetivo:** Inicializar la UI de Astro con soporte de React.
- **Input:** Directorio de trabajo del monorepo.
- **Output:** Carpeta `frontend/` con configuración base de Astro y React instalados.
- **Proceso:**
  1. Ejecutar en terminal: `npx -y create-astro@latest ./frontend -- --template minimal --install-dependencies npm --no-git`.
  2. Integrar React ejecutando: `npx astro add react -y` dentro de `frontend/`.
- **Tests:** Ejecutar `npm run dev` en `frontend/`.
- **AC:** El servidor de desarrollo Astro inicializa en `http://localhost:4321` y entrega HTML válido.

#### [X] A0.1.1.2 — Scaffold del Gateway (Rust Axum)
- **Objetivo:** Crear la aplicación de Rust que gestionará las conexiones HTTP y WebSocket.
- **Input:** Directorio del monorepo.
- **Output:** Carpeta `gateway/` con `Cargo.toml` estructurado.
- **Proceso:**
  1. Ejecutar en raíz del monorepo: `cargo new ./gateway --bin`.
  2. Modificar `Cargo.toml` para incluir dependencias críticas: `axum`, `tokio` (features full), `serde`, `serde_json`, `glam` (matemáticas 3D), `tower-http` (CORS).
- **Tests:** Ejecutar `cargo check` dentro de `gateway/`.
- **AC:** El código base compila exitosamente y sin advertencias o lints críticos.

#### [X] A0.1.1.3 — Scaffold del Servidor de Pose (FastAPI Python)
- **Objetivo:** Crear el entorno virtual y configuración de dependencias de Python.
- **Input:** Directorio del monorepo.
- **Output:** Archivo `services/realtime/ms_pose_rt/requirements.txt` y estructura inicial.
- **Proceso:**
  - Crear la ruta `services/realtime/ms_pose_rt/`.
  - Crear `requirements.txt` con: `fastapi`, `uvicorn`, `mediapipe`, `opencv-python-headless`, `pydantic`.
- **Tests:** Instalar dependencias mediante `pip install -r requirements.txt` en un entorno virtual limpio de Python 3.10.
- **AC:** La instalación de dependencias finaliza con código de salida 0.

---

### [X] T0.1.2 — Setup de Docker Compose
- **Objetivo:** Definir e instrumentar la orquestación local del backend y la IA.
- **AC:** Conexión HTTP interna verificada entre Gateway y Pose RT.

#### [X] A0.1.2.1 — Orquestación Docker Compose MVP
- **Objetivo:** Escribir el `docker-compose.yml` para los servicios de Backend y Detección de Pose.
- **Input:** Rutas de Gateway y de FastAPI.
- **Output:** Archivo `docker-compose.yml` en la raíz y Dockerfiles de soporte.
- **Proceso:**
  1. Escribir un Dockerfile multi-stage ligero para `gateway` basado en `rust:1.78` (compilación) y `debian:bookworm-slim` (ejecución).
  2. Escribir Dockerfile para `ms_pose_rt` basado en `python:3.10-slim`.
  3. Crear `docker-compose.yml` mapeando puertos `8080:8080` (Gateway) y `8001:8001` (Pose RT).
- **Tests:** Ejecutar `docker-compose up --build -d` en la raíz.
- **AC:** Los contenedores inician e imprimen logs de estado en la consola.

---

## [ ] Fase 1 — Protocolo de Comunicación y Modelado de Datos

- **Objetivo:** Codificar las estructuras y esquemas tipados que estructurarán el intercambio de frames e inferencias.
- **AC global de la Fase:** Las tres bases de código (TypeScript, Rust, Python) comparten y validan con rigor las mismas definiciones contractuales JSON.

---

### [ ] Sub Fase 1.1 — Mapeo de Payload de WebSocket (WS) e Inferencia

- **Objetivo:** Definir el canal bidireccional asíncrono y los Landmarks.
- **AC global de la Sub Fase:** Los payloads serializados se deserializan en backend y frontend sin pérdidas de precisión matemática.

#### [ ] T1.1.1 — Definición de Mensajes JSON y Keypoints
- **Objetivo:** Crear los modelos para `FrameMessage` (subida de frame) y `PoseResultMessage` (rotaciones de hueso).
- **AC:** Validaciones de instanciación estrictas para todos los DTOs.

#### [ ] A1.1.1.1 — Definición de Tipos en TypeScript (Frontend)
- **Objetivo:** Tipar los payloads de WebSocket para React.
- **Input:** Contrato de WebSocket del plan mínimo.
- **Output:** Archivo `frontend/src/hooks/useWebSocket.ts` o tipos asociados.
- **Proceso:**
  - Definir interfaces `FrameMessage` (con `frame_id`, `data` Base64) y `PoseResultMessage` (con `bone_rotations` conteniendo `quaternion: [number, number, number, number]`).
- **Tests:** Compilación estática de TypeScript mediante `npm run build` o `npx tsc`.
- **AC:** TypeScript valida la correcta asignación de tipos sin advertencias.

#### [ ] A1.1.1.2 — Estructuras Serde en Rust (Gateway)
- **Objetivo:** Modelar y deserializar eficientemente los payloads en Rust.
- **Input:** Contrato JSON.
- **Output:** Módulo `gateway/src/models/ws_messages.rs`.
- **Proceso:**
  - Crear structs con macros `#[derive(Serialize, Deserialize)]` correspondientes a `FrameMessage` y `PoseResultMessage`.
- **Tests:** Crear test unitario en Rust que deserialize un string JSON simulado y compare los campos.
- **AC:** `cargo test` aprueba la deserialización exacta del cuaternión.

---

## [ ] Fase 2 — Microservicio de Inferencia de Pose en Tiempo Real

- **Objetivo:** Implementar la captura, decodificación e inferencia de landmarks de MediaPipe a través del endpoint expuesto de FastAPI en menos de 10ms.
- **AC global de la Fase:** El endpoint `/detect-pose` recibe un frame codificado Base64 de una persona frontal y retorna 13 landmarks clave mapeados correctamente.

---

### [ ] Sub Fase 2.1 — API de MediaPipe y FastAPI

- **Objetivo:** Procesamiento eficiente y ligero en CPU del stream de imágenes.
- **AC global de la Sub Fase:** Latencia promedio de inferencia sostenida en CPU por debajo de los 12ms.

#### [ ] T2.1.1 — Motor de Inferencia de Pose
- **Objetivo:** Decodificar binarios y calcular coordenadas de MediaPipe landmarks.
- **AC:** Extracción de puntos de articulación anatómicos con altos niveles de visibilidad.

#### [ ] A2.1.1.1 — Inferencia con MediaPipe en CPU
- **Objetivo:** Crear el módulo de Python que ejecute la estimación de la pose humana.
- **Input:** Imagen binaria JPEG decodificada.
- **Output:** Listado tipado de Keypoints.
- **Proceso:**
  - Inicializar `mediapipe.solutions.pose.Pose` configurando `static_image_mode=False` y `model_complexity=1` (balance CPU).
  - Decodificar el frame Base64 a NumPy array mediante OpenCV.
  - Procesar imagen y extraer landmarks 3D del cuerpo humano de la lista `results.pose_world_landmarks`.
- **Tests:** Ejecutar script unitario de prueba alimentando una imagen local de prueba.
- **AC:** El script extrae y mapea exitosamente landmarks como `left_shoulder` y `right_shoulder`.

#### [ ] A2.1.1.2 — Endpoint Asíncrono en FastAPI
- **Objetivo:** Crear la API HTTP `/detect-pose` para el consumo del Gateway.
- **Input:** JSON payload de FastAPI.
- **Output:** JSON con landmarks y confianza de estimación.
- **Proceso:**
  - Escribir `services/realtime/ms_pose_rt/main.py` estructurando la API con FastAPI y Pydantic v2.
  - Implementar endpoint `POST /detect-pose` que capture el Base64 y ejecute el estimador.
- **Tests:** Realizar petición HTTP simulada mediante script en Python o comando curl.
- **AC:** Respuesta HTTP con código 200 y JSON estructurado con coordenadas de hombros, codos y muñecas.

---

## [ ] Fase 3 — API Gateway y Motor de Retargeting en Rust

- **Objetivo:** Construir el orquestador Axum en Rust que mantenga el canal del WebSocket activo, comunique bidireccionalmente con el microservicio de Python y calcule la cinemática de huesos con ultra-baja latencia.
- **AC global de la Fase:** El Gateway recibe frames Base64 del WebSocket, consulta al microservicio y despacha las rotaciones de hueso calculadas en un ciclo $< 20ms$.

---

### [ ] Sub Fase 3.1 — WebSocket Server de Axum

- **Objetivo:** Inicializar y gestionar el WebSocket bidireccional interactivo en Rust de forma asíncrona.
- **AC global de la Sub Fase:** Conexiones concurrentes estables y seguras con descarte óptimo de memoria en caídas de conexión.

#### [ ] T3.1.1 — Conector Axum WebSocket
- **Objetivo:** Escribir el gestor de la conexión bidireccional `/ws/live-pose`.
- **AC:** Cliente y Gateway pueden transmitirse mensajes continuos.

#### [ ] A3.1.1.1 — Setup de Servidor Axum WS
- **Objetivo:** Configurar el handshake y enrutamiento del WS.
- **Input:** Conexión HTTPS del navegador.
- **Output:** Módulo `gateway/src/routes/ws_live.rs`.
- **Proceso:**
  - Implementar ruta en Axum usando `WebSocketUpgrade` y crear el loop asíncrono para leer frames de video.
- **Tests:** Conectarse al WebSocket utilizando un cliente de prueba de consola (ej: `websocat`).
- **AC:** Handshake exitoso y conexión WebSocket establecida en puerto `8080`.

---

### [ ] Sub Fase 3.2 — Retargeting de Huesos (glam::Quat)

- **Objetivo:** Implementar los algoritmos de cinemática matemática 3D locales en Rust usando la librería `glam` de alto rendimiento.
- **AC global de la Sub Fase:** El cálculo matemático de los cuaterniones para los 9 huesos humanoid estándar coincide con los valores analíticos canónicos en un margen de tolerancia $\pm 0.001$.

#### [ ] T3.2.1 — Motor de Retargeting Matemático
- **Objetivo:** Calcular rotaciones a partir de diferencias vectoriales tridimensionales de keypoints.
- **AC:** Los vectores resultantes representan con precisión los movimientos angulares reales.

#### [ ] A3.2.1.1 — Algoritmo de Rotación de Huesos
- **Objetivo:** Escribir la conversión espacial en Rust.
- **Input:** Landmark coordenadas del FastAPI.
- **Output:** Arreglo de rotaciones de hueso (`BoneRotation` con Cuaternión `[x, y, z, w]`).
- **Proceso:**
  - Crear módulo `gateway/src/retargeting/math.rs`.
  - Para cada hueso (ej: `LeftArm`), calcular vector unitario real y compararlo con el de Rest Pose (T-Pose).
  - Calcular cuaternión de rotación mínima con `Quat::from_rotation_arc(rest_dir, direction)`.
  - Multiplicar por el cuaternión inverso del hueso padre para obtener la rotación puramente local.
- **Tests:** Crear test unitario alimentando keypoints correspondientes a un brazo levantado $90^\circ$ en el eje Z.
- **AC:** `cargo test` valida que el cuaternión devuelto es aproximadamente `[0.0, 0.0, 0.7071, 0.7071]`.

#### [ ] A3.2.1.2 — Integración de Inferencia y Retargeting en el WebSocket Loop
- **Entregable:** Loop del WS asíncrono integrado de punta a punta.
- **Acciones:**
  - En la recepción de un frame en `ws_live.rs`, serializar a JSON $\rightarrow$ realizar llamada HTTP POST async usando `reqwest` al microservicio `/detect-pose` $\rightarrow$ procesar keypoints devueltos por el motor de retargeting $\rightarrow$ enviar respuesta serializada de vuelta al socket.
- **Tests:** Validar velocidad de procesamiento de un frame simulado en local.
- **AC:** Procesamiento local total (Inferencia + Retargeting) se completa en $< 15ms$.

---

## [ ] Fase 4 — Interfaz de Usuario y Animación WebGL (Astro + R3F)

- **Objetivo:** Desarrollar el frontend interactivo "BioRender Punk" que capture WebRTC en vivo, transmita frames comprimidos y aplique las rotaciones recibidas a los huesos del esqueleto en tiempo real.
- **AC global de la Fase:** El personaje dummy renderizado en el navegador sigue armónicamente los movimientos de la persona detectados frente a la cámara web.

---

### [ ] Sub Fase 4.1 — Estilo Visual "BioRender Punk" y Captura WebRTC

- **Objetivo:** Crear el frontend con estética robusta dark-first y capturar cámara web a 30 FPS.
- **AC global de la Sub Fase:** Transmisión fluida de frames JPEG ligeros sin bloqueos en el hilo principal de renderizado de la UI.

#### [ ] T4.1.1 — Captura y Codificación WebRTC
- **Objetivo:** Capturar frames del navegador y codificarlos en Base64 JPEG de calidad media.
- **AC:** Frames listos para envío inmediato a intervalos constantes.

#### [ ] A4.1.1.1 — LiveCamera React Component
- **Objetivo:** Obtener permisos de cámara y capturar frames del stream.
- **Input:** Permisos multimedia del navegador del usuario.
- **Output:** Componente `frontend/src/components/react/LiveCamera.tsx`.
- **Proceso:**
  - Instanciar video mediante `navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false })`.
  - Dibujar frame en un Canvas oculto de HTML5 y extraer binario codificado mediante `canvas.toDataURL("image/jpeg", 0.6)`.
  - Emitir la cadena Base64 JPEG al WebSocket de forma regular mediante un temporizador `requestAnimationFrame` o `setInterval` de 33ms.
- **Tests:** Mostrar el preview del canvas en pantalla durante desarrollo.
- **AC:** Captura constante a 30 FPS sin pérdidas perceptibles de performance en la página.

#### [ ] A4.1.1.2 — Estilo CSS BioRender Punk
- **Objetivo:** Crear la estética visual oscura en escala de grises con bordes definidos.
- **Input:** Directrices de la guía estética del plan maestro de BioRender.
- **Output:** CSS en `frontend/src/styles/global.css`.
- **Proceso:**
  - Definir fuentes de Google Fonts (IBM Plex Mono para textos, Press Start 2P para títulos).
  - Configurar fondo oscuro rígido (`#171717`), texto claro (`#F5F5F5`), bordes sólidos rígidos sin bordes redondeados.
- **Tests:** Visualizar la landing page en el navegador web local.
- **AC:** La landing page se ve completamente estilizada y premium, libre de colores planos genéricos.

---

### [ ] Sub Fase 4.2 — Renderizado 3D en Tiempo Real (R3F Canvas)

- **Objetivo:** Cargar e interactuar con el modelo humanoid binario, buscando y rotando sus huesos de forma reactiva.
- **AC global de la Sub Fase:** Actualizaciones angulares fluidas en WebGL sin caídas de framerate perceptibles en pantalla.

#### [ ] T4.2.1 — Canvas WebGL e Indexado de Armature
- **Objetivo:** Renderizar el personaje 3D dummy con luces e indexar sus huesos.
- **AC:** Modelo dummy visualizado correctamente y articulado en memoria.

#### [ ] A4.2.1.1 — Componente de Visualización React Three Fiber (`Viewer3D.tsx`)
- **Objetivo:** Inicializar la escena 3D y cargar el modelo humanoid GLB.
- **Input:** Modelo `dummy_humanoid.glb` ubicado en la carpeta pública.
- **Output:** Componente React `frontend/src/components/react/Viewer3D.tsx`.
- **Proceso:**
  - Configurar el Canvas de R3F con luces ambientales y direccionales adecuadas y controles orbitales (`OrbitControls`).
  - Cargar el modelo 3D con `useGLTF` e indexar los huesos en un mapa mutable en memoria (`useRef(new Map())`) recorriendo recursivamente la escena (`scene.traverse`).
- **Tests:** Cargar el componente en una página Astro con hydration `client:only="react"`.
- **AC:** El modelo humanoide renderiza correctamente en el visor sin errores de WebGL o de servidor.

#### [ ] A4.2.1.2 — Aplicación Dinámica de Rotación de Huesos
- **Objetivo:** Rotar los huesos humanoid en base a las respuestas de WebSocket.
- **Input:** Arreglo `bone_rotations` desde el WebSocket.
- **Output:** Rotaciones físicas del esqueleto reflejadas en el canvas WebGL.
- **Proceso:**
  - Escuchar cambios en el estado del WebSocket y recorrer el arreglo de rotaciones recibido.
  - Para cada entrada, buscar el hueso indexado y aplicar su rotación mediante `bone.quaternion.set(x, y, z, w)`.
- **Tests:** Enviar rotaciones de prueba simuladas mediante un mock local.
- **AC:** El modelo 3D mueve los brazos y articulaciones de forma reactiva y sin demoras.

---

## [ ] Fase 5 — Integración de Flujo Completo, Pruebas y Aceptación

- **Objetivo:** Desplegar el stack completo de forma integrada local y certificar la latencia extrema $< 50ms$ y estabilidad de todo el MVP.
- **AC global de la Fase:** Ejecución de pruebas integrales finalizan con éxito y el MVP es declarado completamente funcional y listo para desarrollo superior.

---

### [ ] Sub Fase 5.1 — Integración y Pruebas E2E del MVP

- **Objetivo:** Orquestar de punta a punta y certificar las métricas operativas de BioRender.
- **AC global de la Sub Fase:** El sistema completo corre fluido localmente mediante Docker Compose y el visor 3D responde en tiempo real a los movimientos corporales físicos.

#### [ ] T5.1.1 — Validación del Prototipo MVP
- **Objetivo:** Correr y verificar la solución bajo condiciones reales de uso.
- **AC:** Prototipo validado y estable en local.

#### [ ] A5.1.1.1 — Ejecución del Sistema de Punta a Punta y Certificación de Latencia
- **Objetivo:** Verificar la latencia de ida y vuelta (RTT) del frame de la cámara al render WebGL.
- **Input:** Monorepo local unificado.
- **Output:** Logs de rendimiento y prototipo funcional.
- **Proceso:**
  1. Levantar backend asíncrono con `docker-compose up --build`.
  2. Ejecutar frontend Astro con `npm run dev`.
  3. Acceder en el navegador a `http://localhost:4321` y activar el stream de la cámara web.
  4. Monitorear los tiempos de ida y vuelta del WebSocket imprimendo marcas de tiempo (`console.time`).
- **Tests:** Realizar movimientos físicos de brazos frente a la cámara web.
- **AC:** El avatar 3D imita los movimientos corporales en tiempo real de forma armónica a un framerate fluido ($\ge 24$ FPS sostenidos) y con una latencia de respuesta $< 50ms$ verificada en consola.
