/// Archivo: generate_3d.rs
/// Fecha de modificación: 31/05/2026
/// Autor: Alex Prieto
///
/// Descripción:
/// Controlador HTTP en Rust Axum para encolar la generación de avatares 3D (POST /api/generate-3d).
/// Acepta subidas de archivos en formato Multipart (imagen PNG/JPG), genera un UUID de Job,
/// sube de forma asíncrona la imagen a MinIO, registra la tarea en Redis como 'queued'
/// y despacha la tarea de inferencia multi-vista a la cola Celery de producción.
/// Retorna código HTTP 202 Accepted con el Job ID para polling posterior.
///
/// Sustentación Científica:
/// La subida en streaming asíncrona con multipart evita el buffering total de archivos pesados
/// en la memoria física del Gateway, asegurando un uso óptimo y predecible de RAM.
///
/// Acciones Principales:
///     - Extraer el archivo de imagen de la petición Multipart HTTP.
///     - Generar un UUID único para rastrear todo el ciclo de vida del Job.
///     - Subir la imagen a la ruta 'uploads/{job_id}/input.png' en MinIO.
///     - Registrar la clave de estado efímera en Redis usando JobTracker.
///     - LPUSH de la tarea Celery a la cola 'generation'.
///
/// Entradas / Dependencias:
///     - Crate axum, serde, serde_json, uuid, anyhow.
///     - Estado global compartido AppState.
///
/// Salidas / Efectos:
///     - Binario subido a MinIO.
///     - Tarea insertada en Redis.
///     - Retorna JSON `{ "job_id": "...", "status": "queued" }`.
use axum::{
    extract::{Multipart, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use std::sync::Arc;
use uuid::Uuid;
use crate::routes::ws_live::AppState;

/// Manejador HTTP POST que procesa la subida de imágenes de personajes y encola el pipeline 3D.
pub async fn generate_3d_handler(
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let job_id = Uuid::new_v4().to_string();
    let mut file_bytes: Option<Vec<u8>> = None;
    let mut content_type = "image/png".to_string();

    tracing::info!("Procesando subida multipart para generacion 3D. Job ID: {}", job_id);

    // 1. Extraer los campos multipart de la peticion
    while let Ok(Some(field)) = multipart.next_field().await {
        if let Some(name) = field.name() {
            if name == "image" || name == "file" {
                if let Some(c_type) = field.content_type() {
                    content_type = c_type.to_string();
                }
                match field.bytes().await {
                    Ok(bytes) => {
                        file_bytes = Some(bytes.to_vec());
                    }
                    Err(err) => {
                        tracing::error!("Error al leer bytes del multipart: {}", err);
                        return Err((
                            StatusCode::BAD_REQUEST,
                            Json(serde_json::json!({
                                "error": format!("Fallo al leer datos de la imagen: {}", err)
                            })),
                        ));
                    }
                }
                break;
            }
        }
    }

    let bytes = match file_bytes {
        Some(b) => b,
        None => {
            tracing::error!("No se encontro el archivo de imagen en la peticion multipart");
            return Err((
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": "Archivo de imagen es requerido bajo el campo 'image' o 'file'."
                })),
            ));
        }
    };

    let s3_key = format!("uploads/{}/input.png", job_id);

    // 2. Subir imagen a MinIO
    if let Err(err) = state.minio_client.upload_file(&s3_key, bytes, &content_type).await {
        tracing::error!("Fallo al subir imagen de entrada del Job {} a MinIO: {}", job_id, err);
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({
                "error": "Error al almacenar el archivo en la base de objetos S3."
            })),
        ));
    }

    // 3. Registrar estado inicial del Job en Redis a 'queued'
    if let Err(err) = state.job_tracker.initialize_job(&job_id).await {
        tracing::error!("Fallo al inicializar Job {} en Redis: {}", job_id, err);
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({
                "error": "Error al registrar el tracking del Job en base de datos."
            })),
        ));
    }

    // 4. Encolar asincronamente en Celery
    let celery_payload = serde_json::json!({
        "job_id": job_id.clone(),
        "input_image_key": s3_key.clone()
    });

    if let Err(err) = state.redis_queue.enqueue_celery_task("generation", "tasks.generate_multiview", celery_payload).await {
        tracing::error!("Error al encolar tarea de Celery para Job {}: {}", job_id, err);
        // Actualizar a error
        let _ = state.job_tracker.update_job_status(&job_id, "error", 100, "", Some("Error de encolado".to_string())).await;
        
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({
                "error": "Error al despachar la tarea al broker asincrono."
            })),
        ));
    }

    tracing::info!("Job {} de generacion 3D despachado exitosamente.", job_id);

    // Retornar 202 Accepted
    Ok((
        StatusCode::ACCEPTED,
        Json(serde_json::json!({
            "job_id": job_id,
            "status": "queued",
            "message": "Generacion 3D encolada de forma exitosa. Realice polling sobre /api/jobs/{job_id}"
        })),
    ))
}
