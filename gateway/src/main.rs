//! Módulo: gateway_main
//! Modificación: 2026-05-28
//! Autor: Alex Prieto
//!
//! Descripción:
//! Punto de entrada principal para el API Gateway de BioRender.
//! Inicializa el enrutador de Axum, configura las capas de CORS y
//! levanta el servidor web asíncrono sobre Tokio.
//!
//! # Ejecución:
//! ```bash
//! cargo run --release
//! ```

use std::net::SocketAddr;
use axum::{routing::get, Router};
use tower_http::cors::CorsLayer;

#[tokio::main]
async fn main() {
    // Inicializar el sistema de trazas (logging estructurado)
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();

    tracing::info!("Inicializando BioRender API Gateway...");

    // Configurar rutas
    let app = Router::new()
        .route("/health", get(health_check))
        .layer(CorsLayer::permissive());

    // Configurar dirección de escucha
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
