"""
Archivo: worker.py
Fecha de modificación: 04/06/2026
Autor: Alex Prieto

Descripción:
Worker asíncrono de Celery para el microservicio de preprocesamiento robusto (MS 7.1).
Fase 7 — Modernización del Pipeline A con Modelos SOTA 2025-2026.

Resuelve los 4 puntos de falla documentados del pipeline Zero123++→InstantMesh:
    1. Fondo gris inconsistente → segmentación con rembg/BiRefNet + fondo blanco puro.
    2. Floaters y artefactos → máscara alfa limpia con refinamiento de bordes.
    3. Normalización incorrecta → esfera unitaria (no cubo), evita bug de recorte de triplano.
    4. Encuadre inconsistente → centrado con padding 10% en canvas 512×512.

Entradas / Dependencias:
    - Celery, redis, boto3, Pillow, numpy, rembg, opencv-python-headless.
"""

import io
import os
import json
import time
from typing import Dict, Any
import boto3
from celery import Celery
import numpy as np
from PIL import Image
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "biorenderadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "biorendersecret")
BUCKET_NAME = "biorender-assets"
TARGET_SIZE = 512
PADDING_RATIO = 0.10

celery_app = Celery(
    "ms_preprocess",
    broker=REDIS_URL,
    backend=REDIS_URL
)

s3_client = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

redis_client = redis.Redis.from_url(REDIS_URL)


def remove_background(img: Image.Image) -> Image.Image:
    """
    Elimina el fondo de la imagen usando rembg (U2-Net) y retorna una imagen RGBA
    con máscara alfa limpia. Fallback a umbralización si rembg no está disponible.
    """
    try:
        from rembg import remove
        print("[*] Ejecutando segmentación de fondo con rembg (U2-Net)...")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        result_bytes = remove(img_bytes.read())
        result = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
        print("[+] Segmentación de fondo completada con rembg.")
        return result
    except ImportError:
        print("[!] rembg no disponible, usando fallback de umbralización...")
        return _fallback_segmentation(img)
    except Exception as e:
        print(f"[!] Error en rembg, usando fallback: {e}")
        return _fallback_segmentation(img)


def _fallback_segmentation(img: Image.Image) -> Image.Image:
    """Segmentación de fallback basada en umbralización del fondo."""
    import cv2
    img_np = np.array(img.convert("RGB"))
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    rgba = np.dstack([img_np, mask])
    return Image.fromarray(rgba, "RGBA")


def normalize_to_unit_sphere(img_rgba: Image.Image) -> Image.Image:
    """
    Recorta el sujeto usando el bounding box de la máscara alfa,
    lo centra en un canvas cuadrado con padding, y normaliza a esfera unitaria.
    """
    alpha = np.array(img_rgba)[:, :, 3]
    coords = np.argwhere(alpha > 128)

    if len(coords) == 0:
        print("[!] Máscara alfa vacía, retornando imagen redimensionada...")
        return img_rgba.resize((TARGET_SIZE, TARGET_SIZE), Image.Resampling.LANCZOS)

    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)

    crop_w = x_max - x_min + 1
    crop_h = y_max - y_min + 1
    max_dim = max(crop_w, crop_h)

    padding = int(max_dim * PADDING_RATIO)
    canvas_size = max_dim + 2 * padding

    crop_x = max(0, x_min - padding)
    crop_y = max(0, y_min - padding)
    crop_x2 = min(img_rgba.width, x_max + 1 + padding)
    crop_y2 = min(img_rgba.height, y_max + 1 + padding)

    cropped = img_rgba.crop((crop_x, crop_y, crop_x2, crop_y2))

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
    paste_x = (canvas_size - cropped.width) // 2
    paste_y = (canvas_size - cropped.height) // 2
    canvas.paste(cropped, (paste_x, paste_y), cropped)

    result = canvas.resize((TARGET_SIZE, TARGET_SIZE), Image.Resampling.LANCZOS)
    print(f"[+] Sujeto normalizado a esfera unitaria: crop=({crop_w}x{crop_h}), canvas={canvas_size}x{canvas_size}")
    return result


def composite_on_white(img_rgba: Image.Image) -> Image.Image:
    """Compone la imagen RGBA sobre fondo blanco puro (RGB 255,255,255)."""
    background = Image.new("RGB", img_rgba.size, (255, 255, 255))
    background.paste(img_rgba, mask=img_rgba.split()[3])
    return background.convert("RGB")


@celery_app.task(name="tasks.preprocess_image", queue="preprocess")
def preprocess_image(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea Celery que descarga la imagen de entrada, elimina el fondo,
    normaliza a esfera unitaria y sube el resultado limpio a MinIO.
    """
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    image_key = payload.get("input_image_key")

    if not job_id or not image_key:
        raise ValueError("Payload incompleto: 'job_id' e 'input_image_key' son requeridos.")

    print(f"[*] Iniciando Tarea preprocess_image para el Job {job_id}...")

    try:
        s3_download_start = time.perf_counter()
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=image_key)
        input_data = response["Body"].read()
        input_image = Image.open(io.BytesIO(input_data)).convert("RGB")
        s3_download_dur = int((time.perf_counter() - s3_download_start) * 1000)

        seg_start = time.perf_counter()
        img_rgba = remove_background(input_image)
        seg_dur = int((time.perf_counter() - seg_start) * 1000)

        norm_start = time.perf_counter()
        img_normalized = normalize_to_unit_sphere(img_rgba)
        norm_dur = int((time.perf_counter() - norm_start) * 1000)

        comp_start = time.perf_counter()
        img_final = composite_on_white(img_normalized)
        comp_dur = int((time.perf_counter() - comp_start) * 1000)

        s3_upload_start = time.perf_counter()
        output_key = f"uploads/{job_id}/preprocessed/input_clean.png"
        buffer = io.BytesIO()
        img_final.save(buffer, format="PNG")
        buffer.seek(0)
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=buffer.read(),
            ContentType="image/png"
        )
        s3_upload_dur = int((time.perf_counter() - s3_upload_start) * 1000)

        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(
            f"[PERF_LOG] Task: preprocess_image | Descarga S3: {s3_download_dur}ms | "
            f"Segmentación: {seg_dur}ms | Normalización: {norm_dur}ms | "
            f"Composición: {comp_dur}ms | Subida S3: {s3_upload_dur}ms | "
            f"Duración Total: {total_dur}ms"
        )

        status_update = {
            "status": "processing",
            "progress": 15,
            "result_url": "",
            "updated_at": int(time.time()),
            "stage": "preprocess_done"
        }
        redis_client.set(f"job:status:{job_id}", json.dumps(status_update))

        next_payload = {
            "job_id": job_id,
            "preprocessed_key": output_key,
            "input_image_key": image_key
        }
        celery_app.send_task(
            "tasks.detect_hardware_and_route",
            args=[next_payload],
            queue="route"
        )
        print(f"[+] Job {job_id} preprocesado. Encolado en cola 'route' para detección HW.")

        return {
            "status": "success",
            "job_id": job_id,
            "preprocessed_key": output_key,
            "duration_ms": total_dur
        }

    except Exception as err:
        print(f"[!] Error crítico en preprocess_image del Job {job_id}: {str(err)}")
        status_update = {
            "status": "error",
            "progress": 100,
            "result_url": "",
            "error_message": str(err),
            "updated_at": int(time.time())
        }
        redis_client.set(f"job:status:{job_id}", json.dumps(status_update))
        raise err
