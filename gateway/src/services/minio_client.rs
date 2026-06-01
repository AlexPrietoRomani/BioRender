/// Archivo: minio_client.rs
/// Fecha de modificación: 31/05/2026
/// Autor: Alex Prieto
///
/// Descripción:
/// Proveedor de servicio asíncrono en Rust para interactuar con el Object Storage (MinIO).
/// Proporciona utilidades para inicializar el cliente usando credenciales de entorno,
/// realizar subidas multipart de imágenes/videos y generar URLs pre-firmadas (Presigned URLs)
/// temporales con firmas criptográficas válidas por 1 hora para permitir descargas directas.
///
/// Sustentación Científica:
/// El uso de Presigned URLs es un patrón de diseño crítico para mitigar el cuello de botella
/// de red en el API Gateway. Permite descargar assets binarios pesados (.glb, .mp4)
/// directamente desde el almacenamiento MinIO de forma segura y autorizada.
///
/// Acciones Principales:
///     - Inicializar el cliente S3 compatible con MinIO usando AWS SDK.
///     - Subir búferes de bytes (imágenes, videos) de forma asíncrona.
///     - Generar URLs pre-firmadas ('Presigned GET URL') que expiran en 3600 segundos.
///
/// Entradas / Dependencias:
///     - Crate aws-config, aws-sdk-s3, aws-credential-types, anyhow.
///     - Variables de entorno: MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY.
///
/// Salidas / Efectos:
///     - Binarios transferidos de forma exitosa a MinIO.
///     - Retorna cadenas URI firmadas.
use anyhow::{Context, Result};
use aws_config::BehaviorVersion;
use aws_sdk_s3::primitives::ByteStream;
use aws_sdk_s3::presigning::PresigningConfig;
use std::env;
use std::time::Duration;

#[derive(Clone)]
pub struct MinioClient {
    client: aws_sdk_s3::Client,
    bucket: String,
    public_endpoint: Option<String>,
}

impl MinioClient {
    /// Inicializa un nuevo cliente de S3 configurado para MinIO.
    /// Reintenta la auto-creación del bucket hasta 10 veces con 2 segundos entre intentos
    /// para tolerar el tiempo de arranque de MinIO en Docker.
    pub async fn new() -> Self {
        let endpoint = env::var("MINIO_ENDPOINT").unwrap_or_else(|_| "http://localhost:9000".to_string());
        let access_key = env::var("MINIO_ACCESS_KEY").unwrap_or_else(|_| "biorenderadmin".to_string());
        let secret_key = env::var("MINIO_SECRET_KEY").unwrap_or_else(|_| "biorendersecret".to_string());
        let bucket = env::var("MINIO_BUCKET").unwrap_or_else(|_| "biorender-assets".to_string());
        let public_endpoint = env::var("MINIO_PUBLIC_ENDPOINT").ok();

        let credentials = aws_credential_types::Credentials::new(
            access_key,
            secret_key,
            None,
            None,
            "Static",
        );

        let config = aws_config::defaults(BehaviorVersion::latest())
            .credentials_provider(credentials)
            .endpoint_url(endpoint)
            .region(aws_config::Region::new("us-east-1"))
            .load()
            .await;

        // IMPORTANTE: MinIO requiere path-style (http://host:port/bucket/key).
        // Sin force_path_style, el SDK AWS intenta virtual-hosted-style resolviendo
        // el subdominio "bucket.host" que Docker DNS no conoce, causando DNS error.
        let s3_config = aws_sdk_s3::config::Builder::from(&config)
            .force_path_style(true)
            .build();

        let client = aws_sdk_s3::Client::from_conf(s3_config);

        // Reintentar la auto-creación del bucket hasta 10 veces para tolerar el arranque de MinIO
        tracing::info!("MinIO: Verificando/Creando bucket '{}'...", bucket);
        let max_retries = 10u32;
        let mut created = false;
        for attempt in 1..=max_retries {
            match client.create_bucket().bucket(&bucket).send().await {
                Ok(_) => {
                    tracing::info!("MinIO: Bucket '{}' creado exitosamente en intento {}/{}.", bucket, attempt, max_retries);
                    created = true;
                    break;
                }
                Err(err) => {
                    let err_str = format!("{:?}", err);
                    // BucketAlreadyOwnedByYou / BucketAlreadyExists = el bucket ya existe, OK
                    if err_str.contains("BucketAlreadyOwnedByYou") || err_str.contains("BucketAlreadyExists") {
                        tracing::info!("MinIO: Bucket '{}' ya existe. Continuando.", bucket);
                        created = true;
                        break;
                    } else {
                        tracing::warn!(
                            "MinIO: Intento {}/{} fallido para bucket '{}': {:?}. Reintentando en 2s...",
                            attempt, max_retries, bucket, err
                        );
                        tokio::time::sleep(Duration::from_secs(2)).await;
                    }
                }
            }
        }
        if !created {
            tracing::error!("MinIO: No se pudo crear/verificar el bucket '{}' después de {} intentos. Las subidas fallaran hasta que MinIO sea accesible.", bucket, max_retries);
        }

        Self { client, bucket, public_endpoint }
    }


    /// Sube un archivo binario (búfer de bytes) a una ruta (Key) del bucket.
    pub async fn upload_file(&self, key: &str, data: Vec<u8>, content_type: &str) -> Result<()> {
        let body = ByteStream::from(data);
        self.client
            .put_object()
            .bucket(&self.bucket)
            .key(key)
            .body(body)
            .content_type(content_type)
            .send()
            .await
            .context("Error al subir objeto binario a MinIO/S3")?;
        Ok(())
    }

    /// Genera una URL de descarga pre-firmada (Presigned GET) válida por 1 hora.
    pub async fn generate_presigned_get_url(&self, key: &str) -> Result<String> {
        let expires_in = Duration::from_secs(3600); // 1 hora
        let presigned_req = self.client
            .get_object()
            .bucket(&self.bucket)
            .key(key)
            .presigned(PresigningConfig::expires_in(expires_in).context("Fallo al configurar expiración CORS en firma S3")?)
            .await
            .context("Error al generar firma criptográfica del objeto S3")?;
        
        let mut url_str = presigned_req.uri().to_string();

        if let Some(ref pub_ep) = self.public_endpoint {
            let internal_endpoint = env::var("MINIO_ENDPOINT").unwrap_or_else(|_| "http://biorender-minio:9000".to_string());
            if url_str.contains(&internal_endpoint) {
                url_str = url_str.replace(&internal_endpoint, pub_ep);
            } else {
                url_str = url_str.replace("http://biorender-minio:9000", pub_ep);
            }
        }
        
        Ok(url_str)
    }
}
