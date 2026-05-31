/// Archivo: redis_queue.rs
/// Fecha de modificación: 31/05/2026
/// Autor: Alex Prieto
///
/// Descripción:
/// Productor asíncrono de mensajería Redis para el API Gateway.
/// Modela y serializa payloads de tareas en el formato JSON de trama binaria estricto
/// requerido por Celery. Permite encolar trabajos en las colas 'queue:generation' y
/// 'queue:motion' de forma ágil desde los controladores REST Axum usando Tokio.
///
/// Sustentación Científica:
/// Celery utiliza un protocolo de envoltura serializada sobre brokers AMQP/Redis.
/// Codificar manualmente los headers, correlation IDs de Uuid y el búfer body en base64
/// garantiza que los workers Celery de Python decodifiquen y consuman las tareas
/// de forma nativa sin errores de tipado o deserialización.
///
/// Acciones Principales:
///     - Inicializar la conexión asíncrona a la base de datos Redis.
///     - Serializar argumentos de entrada en la tupla/diccionario requerida por Celery.
///     - Codificar la trama body en Base64 estándar.
///     - Despachar el payload por comando asíncrono `lpush` a Redis.
///
/// Entradas / Dependencias:
///     - Crate redis, serde, serde_json, uuid, base64.
///     - Variables de entorno: REDIS_URL.
///
/// Salidas / Efectos:
///     - Registros de cola insertados en la lista de Redis de la cola correspondiente.
use anyhow::{Context, Result};
use redis::AsyncCommands;
use serde::Serialize;
use uuid::Uuid;

#[derive(Clone)]
pub struct RedisQueue {
    client: redis::Client,
}

#[derive(Serialize)]
struct CeleryMessage {
    body: String,
    #[serde(rename = "content-encoding")]
    content_encoding: String,
    #[serde(rename = "content-type")]
    content_type: String,
    headers: CeleryHeaders,
    properties: CeleryProperties,
}

#[derive(Serialize)]
struct CeleryHeaders {
    id: String,
    task: String,
}

#[derive(Serialize)]
struct CeleryProperties {
    body_encoding: String,
    correlation_id: String,
    delivery_mode: u8,
    delivery_info: DeliveryInfo,
}

#[derive(Serialize)]
struct DeliveryInfo {
    exchange: String,
    routing_key: String,
}

impl RedisQueue {
    /// Crea un nuevo gestor de cola de Redis.
    pub fn new() -> Result<Self> {
        let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string());
        let client = redis::Client::open(redis_url).context("Fallo al inicializar cliente de Redis para colas")?;
        Ok(Self { client })
    }

    /// Encola una tarea en Celery de forma compatible y asíncrona.
    pub async fn enqueue_celery_task<T>(&self, queue_name: &str, task_name: &str, payload: T) -> Result<String>
    where
        T: Serialize,
    {
        let mut conn = self.client.get_async_connection().await.context("No se pudo obtener conexion asincrona a Redis")?;
        let task_id = Uuid::new_v4().to_string();

        // Celery espera que el body sea un JSON array de [ [args], {kwargs}, {embeds} ]
        // En nuestro caso pasamos el payload como el primer y único argumento posicional de la tupla: [payload]
        let celery_args = (vec![payload], serde_json::json!({}), serde_json::json!({
            "callbacks": null,
            "errbacks": null,
            "chain": null,
            "chord": null
        }));

        let json_body = serde_json::to_string(&celery_args).context("Fallo al serializar args de Celery")?;
        
        // Codificar el JSON body a Base64 estándar
        // Para evitar añadir dependencias pesadas de base64, usamos una llamada simple o compresión inline
        // En Rust moderno, de forma nativa podemos usar el crate base64 o un helper
        let base64_body = base64_simd::STANDARD.encode_to_string(json_body.as_bytes());

        let celery_msg = CeleryMessage {
            body: base64_body,
            content_encoding: "utf-8".to_string(),
            content_type: "application/json".to_string(),
            headers: CeleryHeaders {
                id: task_id.clone(),
                task: task_name.to_string(),
            },
            properties: CeleryProperties {
                body_encoding: "base64".to_string(),
                correlation_id: task_id.clone(),
                delivery_mode: 2,
                delivery_info: DeliveryInfo {
                    exchange: "".to_string(),
                    routing_key: queue_name.to_string(),
                },
            },
        };

        let final_payload = serde_json::to_string(&celery_msg).context("Fallo al serializar mensaje completo de Celery")?;
        
        // Celery utiliza por defecto un prefijo en la lista de Redis, ej: "generation"
        let redis_list_key = format!("{}", queue_name);
        
        // Insertar en la cola usando LPUSH asíncrono
        let _: () = conn.lpush(&redis_list_key, final_payload).await
            .context("Error al despachar comando LPUSH en Redis")?;

        tracing::info!("Tarea Celery '{}' encolada con ID: {} en la cola: {}", task_name, task_id, queue_name);
        Ok(task_id)
    }
}
