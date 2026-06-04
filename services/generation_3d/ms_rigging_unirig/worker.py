"""
Archivo: worker.py
Fecha de modificación: 04/06/2026
Autor: Alex Prieto

Descripción:
Worker de auto-rigging con UniRig (MS 7.4a). SIGGRAPH 2025.
Fase 7 — Modernización del Pipeline A con Modelos SOTA 2025-2026.

Reemplaza RigNet por UniRig (Tsinghua + Tripo, arXiv:2504.12451).
Skeleton Tree Tokenization + Bone-Point Cross Attention.
215% improvement en rigging accuracy vs SOTA previo.
Entrenado en Rig-XL (14,000+ modelos rigged).

Nota: Solo checkpoint Articulation-XL2.0 liberado; Rig-XL completo pendiente.
Si UniRig no está disponible, genera esqueleto procedural placeholder.
"""

import io
import os
import json
import time
from typing import Dict, Any
import boto3
from celery import Celery
import numpy as np
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "biorenderadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "biorendersecret")
BUCKET_NAME = "biorender-assets"

celery_app = Celery("ms_rigging_unirig", broker=REDIS_URL, backend=REDIS_URL)

s3_client = boto3.client(
    "s3", endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

redis_client = redis.Redis.from_url(REDIS_URL)

MIXAMO_SKELETON = {
    "joints": [
        {"name": "Hips", "parent": None, "translation": [0, 0, 0]},
        {"name": "Spine", "parent": "Hips", "translation": [0, 0.1, 0]},
        {"name": "Spine1", "parent": "Spine", "translation": [0, 0.12, 0]},
        {"name": "Spine2", "parent": "Spine1", "translation": [0, 0.12, 0]},
        {"name": "Neck", "parent": "Spine2", "translation": [0, 0.15, 0]},
        {"name": "Head", "parent": "Neck", "translation": [0, 0.1, 0]},
        {"name": "LeftShoulder", "parent": "Spine2", "translation": [-0.05, 0.12, 0]},
        {"name": "LeftArm", "parent": "LeftShoulder", "translation": [-0.1, 0, 0]},
        {"name": "LeftForeArm", "parent": "LeftArm", "translation": [-0.25, 0, 0]},
        {"name": "LeftHand", "parent": "LeftForeArm", "translation": [-0.25, 0, 0]},
        {"name": "RightShoulder", "parent": "Spine2", "translation": [0.05, 0.12, 0]},
        {"name": "RightArm", "parent": "RightShoulder", "translation": [0.1, 0, 0]},
        {"name": "RightForeArm", "parent": "RightArm", "translation": [0.25, 0, 0]},
        {"name": "RightHand", "parent": "RightForeArm", "translation": [0.25, 0, 0]},
        {"name": "LeftUpLeg", "parent": "Hips", "translation": [-0.1, -0.05, 0]},
        {"name": "LeftLeg", "parent": "LeftUpLeg", "translation": [0, -0.4, 0]},
        {"name": "LeftFoot", "parent": "LeftLeg", "translation": [0, -0.4, 0]},
        {"name": "LeftToeBase", "parent": "LeftFoot", "translation": [0, -0.05, 0.15]},
        {"name": "RightUpLeg", "parent": "Hips", "translation": [0.1, -0.05, 0]},
        {"name": "RightLeg", "parent": "RightUpLeg", "translation": [0, -0.4, 0]},
        {"name": "RightFoot", "parent": "RightLeg", "translation": [0, -0.4, 0]},
        {"name": "RightToeBase", "parent": "RightFoot", "translation": [0, -0.05, 0.15]},
    ],
    "joint_count": 22,
    "schema": "mixamo_standard"
}


def _load_unirig():
    try:
        from unirig import UniRigPipeline
        print("[*] Cargando UniRig (SIGGRAPH 2025)...")
        pipe = UniRigPipeline.from_pretrained("VAST-AI-Research/UniRig")
        pipe = pipe.to("cuda")
        print("[+] UniRig cargado.")
        return pipe
    except Exception as e:
        print(f"[!] UniRig no disponible: {e}")
        return None


def generate_placeholder_rig() -> Dict[str, Any]:
    """Genera esqueleto Mixamo estándar + skinning weights placeholder."""
    skeleton = MIXAMO_SKELETON.copy()

    num_verts = 1000
    num_joints = skeleton["joint_count"]
    weights = np.zeros((num_verts, num_joints), dtype=np.float32)
    weights[:, 0] = 1.0

    return {
        "skeleton": skeleton,
        "weights": weights.tolist(),
        "vertex_count": num_verts,
        "method": "placeholder_mixamo"
    }


@celery_app.task(name="tasks.rig_mesh_unirig", queue="rigging_unirig")
def rig_mesh_unirig(payload: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    mesh_key = payload.get("mesh_key")

    if not job_id or not mesh_key:
        raise ValueError("Payload incompleto.")

    print(f"[*] Iniciando auto-rigging UniRig para Job {job_id}...")

    try:
        dl_start = time.perf_counter()
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=mesh_key)
        mesh_data = response["Body"].read()
        dl_dur = int((time.perf_counter() - dl_start) * 1000)

        rig_start = time.perf_counter()
        model = _load_unirig()
        if model:
            try:
                result = model.rig(mesh_data)
                rig_result = {
                    "skeleton": result.skeleton,
                    "weights": result.weights.tolist(),
                    "vertex_count": result.vertex_count,
                    "method": "unirig"
                }
            except Exception as e:
                print(f"[!] Error en UniRig: {e}. Fallback a placeholder.")
                rig_result = generate_placeholder_rig()
        else:
            rig_result = generate_placeholder_rig()
        rig_dur = int((time.perf_counter() - rig_start) * 1000)

        ul_start = time.perf_counter()
        skeleton_key = f"uploads/{job_id}/rigged_unirig/skeleton.json"
        weights_key = f"uploads/{job_id}/rigged_unirig/weights.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME, Key=skeleton_key,
            Body=json.dumps(rig_result["skeleton"], indent=2),
            ContentType="application/json"
        )
        s3_client.put_object(
            Bucket=BUCKET_NAME, Key=weights_key,
            Body=json.dumps(rig_result["weights"]),
            ContentType="application/json"
        )
        ul_dur = int((time.perf_counter() - ul_start) * 1000)

        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(f"[PERF_LOG] Task: rig_mesh_unirig | Descarga: {dl_dur}ms | Rigging: {rig_dur}ms | Subida: {ul_dur}ms | Total: {total_dur}ms")

        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "processing", "progress": 75, "result_url": "",
            "updated_at": int(time.time()), "stage": "rigging_done"
        }))

        celery_app.send_task("tasks.validate_rig", args=[{
            "job_id": job_id,
            "mesh_key": mesh_key,
            "skeleton_key": skeleton_key,
            "weights_key": weights_key,
            "route_info": payload.get("route_info", {})
        }], queue="rig_validation")

        return {"status": "success", "job_id": job_id, "duration_ms": total_dur}

    except Exception as err:
        print(f"[!] Error en rig_mesh_unirig Job {job_id}: {err}")
        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "error", "progress": 100, "result_url": "",
            "error_message": str(err), "updated_at": int(time.time())
        }))
        raise err
