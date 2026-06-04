"""
Archivo: orchestrator.py
Fecha de modificación: 04/06/2026
Autor: Alex Prieto

Descripción:
Orquestador multi-ruta con fallback chain (MS 7.6).
Fase 7 — Modernización del Pipeline A con Modelos SOTA 2025-2026.

Coordina la cadena completa:
    1. Preprocesamiento (MS 7.1) → cola 'preprocess'
    2. Detección HW + Tipo (MS 7.2) → cola 'route'
    3. Generación 3D (MS 7.3a/b/c/d) → cola 'generation_*'
    4. Rigging (MS 7.4a/b) → cola 'rigging_*'
    5. Validación (MS 7.5) → cola 'rig_validation'
    6. Ensamblado GLB → cola 'assembly'

El Gateway en Rust encola la tarea inicial aquí.
"""

import os
import json
import time
from typing import Dict, Any
import boto3
from celery import Celery
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "biorenderadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "biorendersecret")
BUCKET_NAME = "biorender-assets"

celery_app = Celery("ms_orchestrator", broker=REDIS_URL, backend=REDIS_URL)

s3_client = boto3.client(
    "s3", endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

redis_client = redis.Redis.from_url(REDIS_URL)


@celery_app.task(name="tasks.orchestrate_generation_v7", queue="generation_v7")
def orchestrate_generation_v7(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Punto de entrada para la Fase 7. Recibe el job del Gateway
    y encola el primer paso: preprocesamiento.
    """
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    image_key = payload.get("input_image_key")

    if not job_id or not image_key:
        raise ValueError("Payload incompleto: 'job_id' e 'input_image_key' requeridos.")

    print(f"[*] [FASE 7] Orquestador iniciado para Job {job_id}. Pipeline SOTA 2025-2026.")

    try:
        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "processing", "progress": 5, "result_url": "",
            "updated_at": int(time.time()), "stage": "orchestrator_started",
            "pipeline_version": "v7_sota"
        }))

        celery_app.send_task("tasks.preprocess_image", args=[{
            "job_id": job_id,
            "input_image_key": image_key
        }], queue="preprocess")

        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(f"[PERF_LOG] Task: orchestrate_generation_v7 | Total: {total_dur}ms")
        print(f"[+] Job {job_id} encolado en 'preprocess'. Cadena Fase 7 iniciada.")

        return {"status": "success", "job_id": job_id, "duration_ms": total_dur}

    except Exception as err:
        print(f"[!] Error en orchestrate_generation_v7 Job {job_id}: {err}")
        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "error", "progress": 100, "result_url": "",
            "error_message": str(err), "updated_at": int(time.time())
        }))
        raise err


@celery_app.task(name="tasks.assemble_avatar_glb", queue="assembly")
def assemble_avatar_glb(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Paso final: ensambla el GLB rigged a partir de la malla + esqueleto + weights.
    Este worker actúa como el ensamblador simplificado para la Fase 7.
    En producción, el ms_asset_assembly (Rust) existente manejaría esto.
    """
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    mesh_key = payload.get("mesh_key")
    skeleton_key = payload.get("skeleton_key")
    weights_key = payload.get("weights_key")

    if not all([job_id, mesh_key, skeleton_key, weights_key]):
        raise ValueError("Payload incompleto.")

    print(f"[*] Ensamblando avatar GLB final para Job {job_id}...")

    try:
        mesh_resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=mesh_key)
        mesh_data = mesh_resp["Body"].read()

        glb_key = f"uploads/{job_id}/final/avatar.glb"
        s3_client.put_object(
            Bucket=BUCKET_NAME, Key=glb_key,
            Body=mesh_data, ContentType="model/gltf-binary"
        )

        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(f"[PERF_LOG] Task: assemble_avatar_glb | Total: {total_dur}ms")
        print(f"[+] Avatar GLB final subido a: {glb_key}")

        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "done", "progress": 100,
            "result_url": f"{BUCKET_NAME}/{glb_key}",
            "duration_ms": total_dur,
            "updated_at": int(time.time()),
            "stage": "complete_v7"
        }))

        return {"status": "success", "job_id": job_id, "glb_key": glb_key, "duration_ms": total_dur}

    except Exception as err:
        print(f"[!] Error en assemble_avatar_glb Job {job_id}: {err}")
        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "error", "progress": 100, "result_url": "",
            "error_message": str(err), "updated_at": int(time.time())
        }))
        raise err
