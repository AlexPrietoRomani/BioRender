/// Archivo: job_tracker.rs
/// Fecha de modificación: 31/05/2026
/// Autor: Alex Prieto
///
/// Descripción:
/// Gestor asíncrono en Rust para el seguimiento y actualización de estados de Jobs.
/// Interactúa directamente con Redis, serializando y deserializando payloads JSON
/// bajo la clave 'job:status:{job_id}' para coordinar y notificar el progreso
/// de los flujos tridimensionales asíncronos al frontend del navegador.
///
/// Sustentación Científica:
/// Mantener una máquina de estados estricta y efímera en Redis previene colisiones
/// o carreras críticas de transiciones de tareas. El estado de polling no bloqueante
/// desde el cliente reduce el coste computacional y provee una experiencia reactiva.
///
/// Acciones Principales:
///     - Inicializar el estado de un nuevo Job a 'queued' con progreso 0%.
///     - Actualizar transiciones de estado a 'processing', 'done' o 'error'.
///     - Consultar y retornar el JSON del Job actual de forma asíncrona.
///
/// Entradas / Dependencias:
///     - Crate redis, serde, serde_json, anyhow.
///     - Variables de entorno: REDIS_URL.
///
/// Salidas / Efectos:
///     - Modificación de las claves 'job:status:{job_id}' en Redis.
use anyhow::{Context, Result};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use std::time::SystemTime;

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct JobStatus {
    pub status: String,
    pub progress: u8,
    pub result_url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_message: Option<String>,
    pub updated_at: u64,
}

#[derive(Clone)]
pub struct JobTracker {
    client: redis::Client,
}

impl JobTracker {
    /// Inicializa un nuevo JobTracker de Redis.
    pub fn new() -> Result<Self> {
        let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string());
        let client = redis::Client::open(redis_url).context("Fallo al inicializar cliente de Redis para JobTracker")?;
        Ok(Self { client })
    }

    /// Obtiene el timestamp Unix actual en segundos.
    fn get_current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }

    /// Inicializa un nuevo Job en Redis con estado 'queued' y 0% de progreso.
    pub async fn initialize_job(&self, job_id: &str) -> Result<()> {
        let mut conn = self.client.get_async_connection().await.context("No se pudo conectar a Redis en JobTracker")?;
        let status = JobStatus {
            status: "queued".to_string(),
            progress: 0,
            result_url: "".to_string(),
            error_message: None,
            updated_at: Self::get_current_timestamp(),
        };

        let json_value = serde_json::to_string(&status).context("Fallo al serializar estado inicial del Job")?;
        let redis_key = format!("job:status:{}", job_id);

        let _: () = conn.set(&redis_key, json_value).await
            .context("Error al escribir estado inicial en Redis")?;
        Ok(())
    }

    /// Obtiene el estado actual de un Job en Redis. Retorna None si no existe.
    pub async fn get_job_status(&self, job_id: &str) -> Result<Option<JobStatus>> {
        let mut conn = self.client.get_async_connection().await.context("No se pudo conectar a Redis en JobTracker")?;
        let redis_key = format!("job:status:{}", job_id);
        
        let json_str: Option<String> = conn.get(&redis_key).await
            .context("Error al obtener estado de Job desde Redis")?;

        match json_str {
            Some(json) => {
                let status: JobStatus = serde_json::from_str(&json).context("Fallo al deserializar JobStatus JSON")?;
                Ok(Some(status))
            }
            None => Ok(None),
        }
    }

    /// Actualiza el estado y progreso de un Job de forma asíncrona.
    pub async fn update_job_status(&self, job_id: &str, new_status: &str, progress: u8, result_url: &str, error_message: Option<String>) -> Result<()> {
        let mut conn = self.client.get_async_connection().await.context("No se pudo conectar a Redis en JobTracker")?;
        let status = JobStatus {
            status: new_status.to_string(),
            progress,
            result_url: result_url.to_string(),
            error_message,
            updated_at: Self::get_current_timestamp(),
        };

        let json_value = serde_json::to_string(&status).context("Fallo al serializar estado del Job")?;
        let redis_key = format!("job:status:{}", job_id);

        let _: () = conn.set(&redis_key, json_value).await
            .context("Error al actualizar estado en Redis")?;
        Ok(())
    }
}
