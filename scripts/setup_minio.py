"""
Archivo: setup_minio.py
Fecha de modificación: 31/05/2026
Autor: Alex Prieto

Descripción:
Script de automatización para inicializar el bucket del Object Storage local (MinIO).
Verifica la conexión con el servidor compatible de Amazon S3, crea el bucket principal
'biorender-assets' si no existe, y le aplica directivas de políticas CORS permisivas y
políticas de lectura pública (Anonymous Read) para posibilitar descargas directas y
subidas multipart desde el navegador frontend.

Sustentación Científica:
La arquitectura de almacenamiento basada en S3 con políticas CORS permite la carga de
objetos directa desde el navegador (presigned URLs/CORS), aliviando la carga del Gateway
Rust, lo que representa un patrón cloud-native robusto y escalable.

Acciones Principales:
    - Autodetectar y conectar con la API de MinIO usando boto3.
    - Comprobar la existencia del bucket 'biorender-assets' y crearlo en su ausencia.
    - Establecer políticas de CORS que permitan peticiones externas del frontend.
    - Configurar la política de bucket a lectura anónima para descarga directa.

Entradas / Dependencias:
    - Variables de entorno: MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY.
    - Librería boto3 y botocore de Python.

Salidas / Efectos:
    - Bucket 'biorender-assets' inicializado y configurado en el servidor MinIO.

Ejecución:
    python setup_minio.py

Ejemplo de Uso:
    python setup_minio.py
"""

import json
import os
import sys
import time
from typing import Any
import boto3
from botocore.client import Config
from botocore.exceptions import EndpointConnectionError, ClientError

# Configuración inicializada mediante variables de entorno o valores predeterminados
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "biorenderadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "biorendersecret")
BUCKET_NAME = "biorender-assets"


def initialize_s3_client() -> boto3.client:
    """
    Inicializa el cliente de boto3 compatible con la API de MinIO.

    Returns:
        boto3.client: Cliente configurado para conectarse al Object Storage.
    """
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1"
    )


def setup_bucket_cors(s3_client: Any, bucket: str) -> None:
    """
    Establece las directivas de CORS laxas para habilitar descargas directas del navegador.

    Args:
        s3_client (boto3.client): Cliente de S3 inicializado.
        bucket (str): Nombre del bucket a configurar.
    """
    cors_configuration = {
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["GET", "POST", "PUT", "DELETE", "HEAD"],
                "AllowedOrigins": ["*"],
                "ExposeHeaders": ["ETag"]
            }
        ]
    }
    s3_client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration=cors_configuration
    )


def setup_bucket_policy(s3_client: Any, bucket: str) -> None:
    """
    Aplica una política de bucket para lectura pública (anónima).

    Args:
        s3_client (boto3.client): Cliente de S3 inicializado.
        bucket (str): Nombre del bucket a configurar.
    """
    # Política en formato JSON que permite GET anónimo sobre todos los recursos del bucket
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*"
            }
        ]
    }
    
    s3_client.put_bucket_policy(
        Bucket=bucket,
        Policy=json.dumps(bucket_policy)
    )


def main() -> None:
    """
    Orquestador principal para la inicialización y validación del bucket de almacenamiento.
    """
    print(f"[*] Conectando a MinIO en el endpoint: {MINIO_ENDPOINT}...")
    s3_client = initialize_s3_client()
    
    max_retries = 5
    retry_delay = 3
    connected = False
    
    # Intentar conexión con reintentos para dar soporte al arranque asíncrono en Docker
    for attempt in range(1, max_retries + 1):
        try:
            s3_client.list_buckets()
            connected = True
            break
        except (EndpointConnectionError, ClientError) as conn_err:
            print(f"[!] Intento {attempt}/{max_retries} fallido: {str(conn_err)}")
            if attempt < max_retries:
                print(f"[*] Esperando {retry_delay} segundos para reintentar...")
                time.sleep(retry_delay)
                
    if not connected:
        print("[!] Error fatal: No se pudo establecer conexión con el servidor MinIO.")
        sys.exit(1)
        
    try:
        # Verificar si el bucket ya existe
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print(f"[*] El bucket '{BUCKET_NAME}' ya se encuentra creado.")
    except ClientError as cli_err:
        # Si el bucket no existe, head_bucket lanza un error 404
        error_code = cli_err.response["Error"]["Code"]
        if error_code in ["404", "NoSuchBucket"]:
            print(f"[*] Creando el bucket '{BUCKET_NAME}'...")
            try:
                s3_client.create_bucket(Bucket=BUCKET_NAME)
                print(f"[+] Bucket '{BUCKET_NAME}' creado exitosamente.")
            except Exception as creation_err:
                print(f"[!] Error al crear el bucket: {str(creation_err)}")
                sys.exit(1)
        else:
            print(f"[!] Error inesperado de cliente S3: {str(cli_err)}")
            sys.exit(1)
            
    # Configurar CORS y políticas de acceso
    try:
        print("[*] Aplicando configuraciones de CORS laxas...")
        setup_bucket_cors(s3_client, BUCKET_NAME)
        
        print("[*] Aplicando política de lectura pública anónima...")
        setup_bucket_policy(s3_client, BUCKET_NAME)
        
        print("[+] Bucket creado y configurado con éxito.")
        sys.exit(0)
    except Exception as policy_err:
        print(f"[!] Error al configurar las políticas del bucket: {str(policy_err)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
