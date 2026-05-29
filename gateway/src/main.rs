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

use std::net::SocketAddr;
use std::sync::Arc;
use axum::{
    routing::get,
    Router,
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

    // Crear el estado compartido
    let shared_state = Arc::new(AppState {
        http_client,
        pose_service_url,
    });

    // Configurar rutas de Axum
    let app = Router::new()
        .route("/health", get(health_check))
        .route("/ws/live-pose", get(ws_handler))
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
