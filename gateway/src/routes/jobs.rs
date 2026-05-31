//! Módulo: routes::jobs
//! Modificación: 2026-05-31
//! Autor: Alex Prieto
//!
//! Descripción:
//! Controlador HTTP en Rust Axum para consultar el estado de los trabajos asíncronos (GET /api/jobs/{id}).
//! Consulta el estado actual en Redis a través de JobTracker. Si el trabajo ha finalizado con éxito,
//! genera dinámicamente una URL pre-firmada (Presigned URL) para permitir al frontend descargar
//! de forma segura el asset resultante (.glb o .mp4) directamente de MinIO sin exponer credenciales.
//!
//! Estructura Interna:
//! - `get_job_status_handler`: Manejador HTTP Axum para el endpoint GET `/api/jobs/{id}`.

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use std::sync::Arc;
use crate::routes::ws_live::AppState;

/// Manejador HTTP GET que consulta el progreso y estado de un Job por su ID.
///
/// Si el estado es "done" y el resultado apunta a una ruta/key en MinIO,
/// genera dinámicamente una URL pre-firmada que expira en 1 hora.
pub async fn get_job_status_handler(
    State(state): State<Arc<AppState>>,
    Path(job_id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    tracing::info!("Consultando estado del Job ID: {}", job_id);

    match state.job_tracker.get_job_status(&job_id).await {
        Ok(Some(mut job_status)) => {
            // Si el estado es "done" y tenemos una key de S3, generamos la URL firmada al vuelo
            if job_status.status == "done" && !job_status.result_url.is_empty() && !job_status.result_url.starts_with("http") {
                match state.minio_client.generate_presigned_get_url(&job_status.result_url).await {
                    Ok(presigned_url) => {
                        job_status.result_url = presigned_url;
                    }
                    Err(err) => {
                        tracing::warn!("No se pudo generar URL firmada para la key '{}' del Job {}: {}", job_status.result_url, job_id, err);
                        // No fallamos la petición completa, pero logueamos la advertencia
                    }
                }
            }

            Ok(Json(job_status))
        }
        Ok(None) => {
            tracing::warn!("Job {} no encontrado en Redis.", job_id);
            Err((
                StatusCode::NOT_FOUND,
                Json(serde_json::json!({
                    "error": format!("El Job {} no existe.", job_id)
                })),
            ))
        }
        Err(err) => {
            tracing::error!("Error al interactuar con Redis para obtener Job {}: {}", job_id, err);
            Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({
                    "error": "Error interno al consultar el estado del trabajo en base de datos."
                })),
            ))
        }
    }
}
