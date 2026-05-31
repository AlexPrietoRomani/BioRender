//! Módulo: routes
//! Modificación: 2026-05-31
//! Autor: Alex Prieto
//!
//! Descripción:
//! Punto de entrada y declaración de los controladores de rutas del API Gateway.
//! Expone los endpoints de WebSocket en vivo, generación 3D, procesamiento de video y
//! el monitor del estado de los trabajos.

pub mod ws_live;
pub mod generate_3d;
pub mod process_video;
pub mod jobs;
