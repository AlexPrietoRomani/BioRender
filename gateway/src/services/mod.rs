//! Módulo: services
//! Modificación: 2026-05-31
//! Autor: Alex Prieto
//!
//! Descripción:
//! Punto de entrada y declaración de los módulos de servicios del API Gateway.
//! Expone el cliente MinIO, el encolador de Redis y el rastreador de estado de trabajos.

pub mod minio_client;
pub mod redis_queue;
pub mod job_tracker;
