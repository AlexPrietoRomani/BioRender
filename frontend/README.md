# BioRender - Frontend Application (Astro + React + WebGL)

Esta es la aplicación web frontend de **BioRender**, construida utilizando **Astro 5** e islas interactivas de **React 19** con **React Three Fiber (R3F)** y **Three.js** para el renderizado tridimensional fluido en tiempo real.

---

## 🚀 Arquitectura y Tecnologías Clave

*   **Astro 5**: Proporciona el andamiaje del sitio estático con soporte modular de alto rendimiento y renderizado selectivo de componentes interactivos (islas).
*   **React 19 & React Three Fiber (R3F)**: Renderizador WebGL declarativo sobre Three.js que permite dibujar el canvas tridimensional, cargar modelos de personajes `.glb` y realizar rotaciones articulares continuas.
*   **Captura e Ingress Bypass por WebSocket (Windows Portability)**:
    *   Para evitar las limitaciones de acceso de Docker a dispositivos USB locales (cámara física `/dev/video0`) en hosts Windows/WSL2, implementamos un proxy de Ingress.
    *   La cámara web del cliente es capturada de forma 100% nativa en el navegador mediante la API de JavaScript `navigator.mediaDevices.getUserMedia()`.
    *   Los frames son dibujados en un canvas oculto, comprimidos a JPEG de baja resolución y serializados a Base64.
    *   Se transmiten por un WebSocket persistente al API Gateway de Rust, que los enruta y devuelve las rotaciones angulares estimadas para animar el avatar en tiempo real en la vista 3D.

---

## 📁 Estructura del Proyecto

```text
frontend/
├── public/                # Fixtures, modelos GLB de prueba y logos estáticos
├── src/
│   ├── components/
│   │   ├── react/         # Componentes interactivos de React (Visor 3D, Uploader, Webcam)
│   │   │   ├── LiveCamera.tsx     # Captura de webcam y envío WebSocket
│   │   │   ├── Viewer3D.tsx       # Canvas de R3F y animación del personaje
│   │   │   ├── ImageUploader.tsx  # Carga multipart para Pipeline A (POST)
│   │   │   └── VideoUploader.tsx  # Carga multipart para Pipeline B (POST)
│   │   └── astro/         # Componentes estáticos de Astro (Layouts, Header, Footer)
│   ├── layouts/           # Plantillas base HTML de la aplicación
│   └── pages/
│       └── index.astro    # Página principal (Dashboard "BioRender Punk")
├── package.json           # Manifiesto de dependencias y scripts de PNPM
└── tsconfig.json          # Configuración del compilador de TypeScript
```

---

## ⚙️ Configuración y Variables de Entorno

Crea un archivo `.env` en la raíz de la carpeta `frontend/` (o a nivel de monorepo) con los siguientes valores de desarrollo:

```env
# URL base para las peticiones HTTP del Gateway de Rust
PUBLIC_GATEWAY_HTTP_URL=http://localhost:8080

# URL base para la conexión WebSocket del flujo de cámara en vivo
PUBLIC_GATEWAY_WS_URL=ws://localhost:8080/ws/live-pose
```

---

## 🧞 Comandos de Ejecución

Todos los comandos se corren desde la raíz de esta carpeta o mediante el gestor monorepo `pnpm`:

| Comando | Acción |
| :--- | :--- |
| `pnpm install` | Instala todas las dependencias del frontend. |
| `pnpm run dev` | Inicia el servidor de desarrollo local en `http://localhost:4321`. |
| `pnpm run build` | Compila los estáticos optimizados y listos para producción en `./dist/`. |
| `pnpm run preview` | Pre-visualiza la compilación de producción de forma local. |
| `pnpm run astro check` | Realiza una comprobación sintáctica y de TypeScript en todo el frontend. |

---

## 🎨 Estética de Diseño: "BioRender Punk"

La interfaz sigue los estándares premium de diseño moderno del monorepo:
*   **Gama de Colores:** Fondo oscuro mate (`#0a0a0c`), acentos en verde neón de baja saturación (`#00f07f`), gris acero cepillado y tipografías legibles.
*   **Tipografía:** IBM Plex Mono e Inter para un aspecto tecnológico, de precisión y de alto rendimiento.
*   **Interacciones:** Bordes rígidos de 2px, animaciones fluidas al pasar el cursor y retroalimentación inmediata mediante barras de progreso en porcentaje.
