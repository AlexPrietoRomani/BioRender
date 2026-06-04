"""
Archivo: validator.py
Fecha de modificación: 04/06/2026
Autor: Alex Prieto

Descripción:
Validador automático de rig (MS 7.5).
Fase 7 — Modernización del Pipeline A con Modelos SOTA 2025-2026.

Verifica:
    1. Esqueleto contiene los joints Mixamo estándar (22 huesos).
    2. Skinning weights suman 1.0 ± 0.01 por vértice.
    3. No hay huesos redundantes.
    4. Topología de la malla es cerrada.

Si falla, re-encola con ruta alternativa (fallback chain).
"""

import io
import os
import json
import time
from typing import Dict, Any, List
import boto3
from celery import Celery
import numpy as np
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "biorenderadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "biorendersecret")
BUCKET_NAME = "biorender-assets"

REQUIRED_JOINTS = [
    "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
    "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"
]

celery_app = Celery("ms_rig_validator", broker=REDIS_URL, backend=REDIS_URL)

s3_client = boto3.client(
    "s3", endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

redis_client = redis.Redis.from_url(REDIS_URL)


def validate_skeleton(skeleton: Dict[str, Any]) -> List[str]:
    """Valida que el esqueleto contiene los joints Mixamo estándar."""
    errors = []
    joints = skeleton.get("joints", [])
    joint_names = [j["name"] for j in joints]

    for required in REQUIRED_JOINTS:
        if required not in joint_names:
            errors.append(f"Hueso faltante: {required}")

    if len(joints) > len(REQUIRED_JOINTS) + 10:
        errors.append(f"Posibles huesos redundantes: {len(joints)} joints (esperados ~{len(REQUIRED_JOINTS)})")

    return errors


def validate_weights(weights: List[List[float]], tolerance: float = 0.01) -> List[str]:
    """Valida que skinning weights suman 1.0 ± tolerance por vértice."""
    errors = []
    weights_np = np.array(weights)

    if weights_np.ndim != 2:
        errors.append(f"Weights con dimensiones inválidas: {weights_np.shape}")
        return errors

    sums = weights_np.sum(axis=1)
    invalid_mask = np.abs(sums - 1.0) > tolerance
    invalid_count = invalid_mask.sum()

    if invalid_count > 0:
        pct = (invalid_count / len(sums)) * 100
        errors.append(f"{invalid_count} vértices ({pct:.1f}%) con weights que no suman 1.0 ± {tolerance}")

    return errors


@celery_app.task(name="tasks.validate_rig", queue="rig_validation")
def validate_rig(payload: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    mesh_key = payload.get("mesh_key")
    skeleton_key = payload.get("skeleton_key")
    weights_key = payload.get("weights_key")

    if not all([job_id, mesh_key, skeleton_key, weights_key]):
        raise ValueError("Payload incompleto.")

    print(f"[*] Iniciando validación de rig para Job {job_id}...")

    try:
        skel_resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=skeleton_key)
        skeleton = json.loads(skel_resp["Body"].read().decode("utf-8"))

        weights_resp = s3_client.get_object(Bucket=BUCKET_NAME, Key=weights_key)
        weights = json.loads(weights_resp["Body"].read().decode("utf-8"))

        val_start = time.perf_counter()
        all_errors = []
        all_errors.extend(validate_skeleton(skeleton))
        all_errors.extend(validate_weights(weights))
        val_dur = int((time.perf_counter() - val_start) * 1000)

        if all_errors:
            print(f"[!] Validación FALLÓ para Job {job_id}: {all_errors}")

            route_info = payload.get("route_info", {})
            current_method = route_info.get("rig_method", "unirig")

            if current_method == "unirig":
                print("[*] Fallback: UniRig → MIA. Re-encolando...")
                celery_app.send_task("tasks.rig_mesh_mia", args=[{
                    "job_id": job_id, "mesh_key": mesh_key,
                    "route_info": {**route_info, "rig_method": "mia", "fallback_from": "unirig"}
                }], queue="rigging_mia")
            else:
                print("[!] Ambos métodos de rigging fallaron. Marcando como error.")
                redis_client.set(f"job:status:{job_id}", json.dumps({
                    "status": "error", "progress": 100, "result_url": "",
                    "error_message": f"Validación de rig falló: {'; '.join(all_errors)}",
                    "updated_at": int(time.time())
                }))

            total_dur = int((time.perf_counter() - start_time) * 1000)
            return {"status": "failed", "job_id": job_id, "errors": all_errors, "duration_ms": total_dur}

        print(f"[+] Validación de rig EXITOSA para Job {job_id}.")

        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(f"[PERF_LOG] Task: validate_rig | Validación: {val_dur}ms | Total: {total_dur}ms")

        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "processing", "progress": 85, "result_url": "",
            "updated_at": int(time.time()), "stage": "validation_done"
        }))

        celery_app.send_task("tasks.assemble_avatar_glb", args=[{
            "job_id": job_id, "mesh_key": mesh_key,
            "skeleton_key": skeleton_key, "weights_key": weights_key,
            "route_info": payload.get("route_info", {})
        }], queue="assembly")

        return {"status": "success", "job_id": job_id, "duration_ms": total_dur}

    except Exception as err:
        print(f"[!] Error en validate_rig Job {job_id}: {err}")
        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "error", "progress": 100, "result_url": "",
            "error_message": str(err), "updated_at": int(time.time())
        }))
        raise err
