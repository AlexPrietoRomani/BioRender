//! Módulo: gateway_main
//! Modificación: 2026-05-29
//! Autor: Alex Prieto
//!
//! Descripción:
//! Punto de entrada principal para el API Gateway de BioRender.
//! Inicializa el enrutador de Axum, configura las capas de CORS, comparte
//! el estado del cliente HTTP y levanta el servidor web asíncrono sobre Tokio,
//! exponiendo los endpoints de salud y WebSocket en tiempo real.
//!
//! # Ejecución:
//! ```bash
//! cargo run --release
//! ```

pub mod models;
pub mod retargeting;
pub mod routes;
pub mod services;

use std::net::SocketAddr;
use std::sync::Arc;
use axum::{
    routing::{get, post},
    Json, Router,
};
use tower_http::cors::CorsLayer;
use reqwest::Client;

use crate::routes::ws_live::{ws_handler, AppState};

#[tokio::main]
async fn main() {
    // Inicializar el sistema de trazas (logging estructurado)
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    tracing::info!("Inicializando BioRender API Gateway...");

    // Leer la URL del microservicio de pose desde las variables de entorno
    let pose_service_url = std::env::var("POSE_SERVICE_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8001".to_string());
    tracing::info!("Pose Service URL configurada: {}", pose_service_url);

    // Inicializar el cliente reqwest reutilizable
    let http_client = Client::builder()
        .build()
        .expect("No se pudo construir el cliente HTTP reqwest");

    // Inicializar servicios de S3 y Redis de forma asíncrona
    let minio_client = services::minio_client::MinioClient::new().await;
    let redis_queue = services::redis_queue::RedisQueue::new()
        .expect("No se pudo conectar a Redis para colas Celery");
    let job_tracker = services::job_tracker::JobTracker::new()
        .expect("No se pudo conectar a Redis para JobTracker");

    // Crear el estado compartido
    let shared_state = Arc::new(AppState {
        http_client,
        pose_service_url,
        minio_client,
        redis_queue,
        job_tracker,
    });

    // Configurar rutas de Axum
    let app = Router::new()
        .route("/", get(welcome_handler))
        .route("/health", get(health_check))
        .route("/ws/live-pose", get(ws_handler))
        .route("/api/generate-3d", post(routes::generate_3d::generate_3d_handler))
        .route("/api/process-video", post(routes::process_video::process_video_handler))
        .route("/api/jobs/:id", get(routes::jobs::get_job_status_handler))
        .with_state(shared_state)
        .layer(CorsLayer::permissive());

    // Configurar dirección de escucha en 0.0.0.0:8080
    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    tracing::info!("Escuchando en http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

/// Manejador para el sanity check de salud del API Gateway.
///
/// Retorna un string plano confirmando que el orquestador está activo.
async fn health_check() -> &'static str {
    "BioRender Rust API Gateway - ACTIVO"
}

/// Manejador de bienvenida para la ruta raíz, evitando el 404 en el navegador.
async fn welcome_handler() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "online",
        "service": "BioRender API Gateway",
        "version": "1.0.0",
        "endpoints": {
            "root": "/",
            "health": "/health",
            "websocket_pose": "/ws/live-pose",
            "generate_3d": "/api/generate-3d",
            "process_video": "/api/process-video",
            "job_status": "/api/jobs/:id"
        }
    }))
}
