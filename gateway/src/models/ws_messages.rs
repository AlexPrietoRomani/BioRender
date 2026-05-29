//! Módulo: models::ws_messages
//! Modificación: 2026-05-29
//! Autor: Alex Prieto
//!
//! Descripción:
//! Define las estructuras de datos serializables con Serde para el intercambio de frames
//! y rotaciones a través de los canales WebSocket y llamadas HTTP.
//!
//! Estructura Interna:
//! - `FrameMessage`: Frame de video entrante en base64 desde el cliente.
//! - `PythonKeypoint`: Coordenadas y visibilidad de articulaciones retornadas por Python.
//! - `PythonPoseResponse`: Datos devueltos por el microservicio de inferencia de pose.
//! - `BoneRotation`: Nombre de articulación y su cuaternión de rotación calculado [x, y, z, w].
//! - `PoseResultMessage`: Payload final enviado al cliente sobre WebSocket.
//!
//! Dependencias Principales:
//! - serde

use serde::{Deserialize, Serialize};

/// Payload del frame enviado por el cliente web
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FrameMessage {
    pub frame_id: i64,
    pub frame_data: String, // JPEG comprimido y codificado en Base64
}

/// Landmark tridimensional retornado por el microservicio de inferencia de pose en Python
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonKeypoint {
    pub name: String,
    pub x: f32,
    pub y: f32,
    pub z: f32,
    pub visibility: f32,
}

/// Respuesta estructurada desde el microservicio de Python FastAPI
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonPoseResponse {
    pub frame_id: i64,
    pub keypoints: Vec<PythonKeypoint>,
    pub confidence: f32,
}

/// Rotación de un hueso específico representado por un cuaternión unitario [x, y, z, w]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoneRotation {
    pub bone_name: String,
    pub quaternion: [f32; 4], // [x, y, z, w]
}

/// Payload del resultado de pose procesado que se transmite de vuelta al cliente
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoseResultMessage {
    pub frame_id: i64,
    pub bone_rotations: Vec<BoneRotation>,
}
