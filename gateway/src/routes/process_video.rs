//! Módulo: routes::process_video
//! Modificación: 2026-05-31
//! Autor: Alex Prieto
//!
//! Descripción:
//! Controlador HTTP en Rust Axum para encolar el procesamiento de video y retargeting (POST /api/process-video).
//! Acepta subidas en Multipart (video MP4/WebM) y el ID del avatar destino, sube el video a MinIO,
//! registra el Job en Redis con estado inicial 'queued' y encola la tarea en la cola Celery de 'motion'.
//! Retorna HTTP 202 Accepted con el Job ID para seguimiento.
//!
//! Estructura Interna:
//! - `process_video_handler`: Manejador HTTP Axum para el endpoint POST `/api/process-video`.

use axum::{
    extract::{Multipart, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use std::sync::Arc;
use uuid::Uuid;
use crate::routes::ws_live::AppState;

/// Manejador HTTP POST que procesa la subida de videos de movimiento y encola el pipeline de retargeting.
pub async fn process_video_handler(
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let start_time = std::time::Instant::now();
    let job_id = Uuid::new_v4().to_string();
    let mut file_bytes: Option<Vec<u8>> = None;
    let mut content_type = "video/mp4".to_string();
    let mut avatar_job_id: Option<String> = None;
    let mut custom_avatar_glb_key: Option<String> = None;

    tracing::info!("Procesando subida multipart para procesamiento de video. Job ID: {}", job_id);

    // 1. Extraer los campos multipart de la petición
    let parse_start = std::time::Instant::now();
    while let Ok(Some(field)) = multipart.next_field().await {
        if let Some(name) = field.name() {
            match name {
                "video" | "file" => {
                    if let Some(c_type) = field.content_type() {
                        content_type = c_type.to_string();
                    }
                    match field.bytes().await {
                        Ok(bytes) => {
                            file_bytes = Some(bytes.to_vec());
                        }
                        Err(err) => {
                            tracing::error!("Error al leer bytes del video: {}", err);
                            return Err((
                                StatusCode::BAD_REQUEST,
                                Json(serde_json::json!({
                                    "error": format!("Fallo al leer datos del video: {}", err)
                                })),
                            ));
                        }
                    }
                }
                "avatar_job_id" | "avatar_id" => {
                    if let Ok(value) = field.text().await {
                        avatar_job_id = Some(value.trim().to_string());
                    }
                }
                "avatar_glb_key" => {
                    if let Ok(value) = field.text().await {
                        custom_avatar_glb_key = Some(value.trim().to_string());
                    }
                }
                _ => {}
            }
        }
    }

    // Validar video bytes
    let bytes = match file_bytes {
        Some(b) => b,
        None => {
            tracing::error!("No se encontró el archivo de video en la petición multipart");
            return Err((
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": "Archivo de video es requerido bajo el campo 'video' o 'file'."
                })),
            ));
        }
    };

    // Resolver avatar_glb_key
    let avatar_glb_key = match (custom_avatar_glb_key, avatar_job_id) {
        (Some(key), _) => key,
        (None, Some(id)) => format!("uploads/{}/final/avatar.glb", id),
        (None, None) => {
            tracing::error!("No se especificó avatar_job_id o avatar_glb_key en la petición");
            return Err((
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": "Debe especificar un 'avatar_job_id' o 'avatar_glb_key' para realizar el retargeting."
                })),
            ));
        }
    };
    let parse_dur = parse_start.elapsed().as_millis();

    let video_key = format!("uploads/{}/input_video.mp4", job_id);

    // 2. Subir video a MinIO
    let upload_start = std::time::Instant::now();
    if let Err(err) = state.minio_client.upload_file(&video_key, bytes, &content_type).await {
        tracing::error!("Fallo al subir video del Job {} a MinIO: {}", job_id, err);
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({
                "error": "Error al almacenar el video en el servidor de objetos S3."
            })),
        ));
    }
    let upload_dur = upload_start.elapsed().as_millis();

    // 3. Registrar estado inicial del Job en Redis a 'queued'
    let init_start = std::time::Instant::now();
    if let Err(err) = state.job_tracker.initialize_job(&job_id).await {
        tracing::error!("Fallo al inicializar Job de video {} en Redis: {}", job_id, err);
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({
                "error": "Error al registrar el tracking del Job en la base de datos."
            })),
        ));
    }
    let init_dur = init_start.elapsed().as_millis();

    // 4. Encolar tarea Celery en la cola 'motion'
    let enqueue_start = std::time::Instant::now();
    let celery_payload = serde_json::json!({
        "job_id": job_id.clone(),
        "avatar_glb_key": avatar_glb_key,
        "video_key": video_key
    });

    if let Err(err) = state.redis_queue.enqueue_celery_task("motion", "tasks.extract_motion", celery_payload).await {
        tracing::error!("Error al encolar tarea de Celery (motion) para Job {}: {}", job_id, err);
        // Actualizar estado a error en Redis
        let _ = state.job_tracker.update_job_status(&job_id, "error", 100, "", Some("Error de encolado".to_string())).await;
        
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({
                "error": "Error al despachar la tarea de movimiento al broker de colas."
            })),
        ));
    }
    let enqueue_dur = enqueue_start.elapsed().as_millis();
    let total_dur = start_time.elapsed().as_millis();

    tracing::info!(
        "[PERF_LOG] Handler: process_video_handler | Parse Multipart: {}ms | Subida S3: {}ms | Inicializacion: {}ms | Encolado: {}ms | Duracion Total: {}ms",
        parse_dur, upload_dur, init_dur, enqueue_dur, total_dur
    );

    // Retornar 202 Accepted con telemetría de rendimiento
    Ok((
        StatusCode::ACCEPTED,
        Json(serde_json::json!({
            "job_id": job_id,
            "status": "queued",
            "duration_ms": total_dur,
            "message": "Procesamiento de video encolado de forma exitosa. Realice polling sobre /api/jobs/{job_id}"
        })),
    ))
}
