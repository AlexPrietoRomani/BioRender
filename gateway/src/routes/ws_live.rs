//! Módulo: routes::ws_live
//! Modificación: 2026-05-29
//! Autor: Alex Prieto
//!
//! Descripción:
//! Controlador WebSocket asíncrono para el API Gateway. Gestiona las conexiones activas,
//! recibe frames de video codificados en JPEG base64, los envía al microservicio de Python
//! para estimar landmarks, calcula el retargeting y devuelve las rotaciones a la UI.
//!
//! Estructura Interna:
//! - `AppState`: Estado compartido del servidor con el cliente HTTP y URL del servicio de pose.
//! - `ws_handler(ws, state)`: Endpoint HTTP de entrada que realiza el handshake del socket.
//! - `handle_socket(socket, state)`: Bucle de lectura y despacho sobre el canal bidireccional.
//!
//! Dependencias Principales:
//! - axum, tokio, reqwest, serde, futures-util

use std::sync::Arc;
use axum::{
    extract::{ws::{Message, WebSocket, WebSocketUpgrade}, State},
    response::IntoResponse,
};
use futures_util::stream::StreamExt;
use futures_util::sink::SinkExt;
use reqwest::Client;

use crate::models::ws_messages::{FrameMessage, PythonPoseResponse, PoseResultMessage};
use crate::retargeting::math::calculate_retargeting;

/// Estado global compartido de la aplicación
pub struct AppState {
    /// Cliente de llamadas HTTP de alto rendimiento reutilizable
    pub http_client: Client,
    /// Endpoint base del microservicio de pose de Python (ej: http://localhost:8001)
    pub pose_service_url: String,
}

/// Manejador de la ruta para actualizar una conexión HTTP estándar a WebSocket.
///
/// # Argumentos
///
/// * `ws` - Extractor de Axum para handshake de WebSocket.
/// * `state` - Estado compartido del gateway envuelto en un puntero atómico `Arc`.
pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_socket(socket, state))
}

/// Orquesta la lectura de tramas y despacho de rotaciones sobre el canal WebSocket establecido.
///
/// # Argumentos
///
/// * `socket` - Conexión de socket activa bidireccional.
/// * `state` - Estado compartido del gateway.
async fn handle_socket(socket: WebSocket, state: Arc<AppState>) {
    let (mut sender, mut receiver) = socket.split();

    tracing::info!("Cliente WebSocket conectado al Hub de Pose.");

    // Bucle continuo para procesar mensajes de texto de la cámara web
    while let Some(Ok(msg)) = receiver.next().await {
        if let Message::Text(text) = msg {
            // 1. Deserializar el FrameMessage que contiene la imagen JPEG base64
            let frame_msg: FrameMessage = match serde_json::from_str(&text) {
                Ok(fm) => fm,
                Err(e) => {
                    tracing::error!("Error deserializando frame message del cliente: {}", e);
                    continue;
                }
            };

            // 2. Preparar el JSON para la llamada REST al microservicio de Python
            let python_payload = serde_json::json!({
                "frame_data": frame_msg.frame_data,
                "frame_id": frame_msg.frame_id
            });

            // 3. Comunicar con el microservicio de inferencia de pose (FastAPI) de forma asíncrona
            let url = format!("{}/detect-pose", state.pose_service_url);
            let response = match state.http_client.post(&url).json(&python_payload).send().await {
                Ok(resp) => resp,
                Err(e) => {
                    tracing::error!("Falla en la llamada HTTP a Pose Service: {}", e);
                    continue;
                }
            };

            // 4. Leer y deserializar landmarks resultantes de MediaPipe
            let python_resp: PythonPoseResponse = match response.json().await {
                Ok(res) => res,
                Err(e) => {
                    tracing::error!("Error deserializando landmarks del microservicio: {}", e);
                    continue;
                }
            };

            // 5. Calcular retargeting cinemático a cuaterniones locales
            let bone_rotations = calculate_retargeting(&python_resp.keypoints);

            // 6. Construir y serializar payload de salida para la interfaz 3D
            let result_msg = PoseResultMessage {
                frame_id: python_resp.frame_id,
                bone_rotations,
            };

            let response_text = match serde_json::to_string(&result_msg) {
                Ok(json) => json,
                Err(e) => {
                    tracing::error!("Error serializando PoseResultMessage de salida: {}", e);
                    continue;
                }
            };

            // 7. Enviar la actualización angular calculada de vuelta al WebSocket del cliente
            if let Err(e) = sender.send(Message::Text(response_text)).await {
                tracing::error!("Conexión WebSocket cerrada al enviar datos: {}", e);
                break;
            }
        }
    }

    tracing::info!("Cliente WebSocket desconectado.");
}
