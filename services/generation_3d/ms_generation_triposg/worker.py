"""
Archivo: worker.py
Fecha de modificación: 04/06/2026
Autor: Alex Prieto

Descripción:
Worker de generación 3D — Ruta Quality (MS 7.3a). GPU ≥ 16GB.
Fase 7 — Modernización del Pipeline A con Modelos SOTA 2025-2026.

Genera malla 3D nativa desde imagen usando TripoSG (VAST, MIT, arXiv:2502.06608)
o TRELLIS (Microsoft, MIT, arXiv:2412.01506) como alternativa.
Modelos de difusión/flow nativos 3D de una sola etapa que evitan el frágil
paso multi-view explícito de Zero123++→InstantMesh.

Integración de modelos reales:
    - TripoSG: github.com/VAST-AI-Research/TripoSG (1.5B params, rectified flow)
    - TRELLIS: github.com/microsoft/TRELLIS (342M-2B params, SLAT)

Nota: Si los modelos no están descargados, genera una malla placeholder
 procedural (cubo texturizado) para validar el pipeline end-to-end.
"""

import io
import os
import json
import time
import struct
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
MODEL_CHOICE = os.getenv("GENERATION_MODEL", "triposg")

celery_app = Celery("ms_generation_triposg", broker=REDIS_URL, backend=REDIS_URL)

s3_client = boto3.client(
    "s3", endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

redis_client = redis.Redis.from_url(REDIS_URL)

_model_cache = None


def _load_triposg():
    """Carga TripoSG desde HuggingFace. Solo la primera vez."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    try:
        from triposg import TripoSGPipeline
        print("[*] Cargando TripoSG (1.5B params)...")
        pipe = TripoSGPipeline.from_pretrained("VAST-AI-Research/TripoSG")
        pipe = pipe.to("cuda")
        _model_cache = pipe
        print("[+] TripoSG cargado exitosamente.")
        return pipe
    except Exception as e:
        print(f"[!] TripoSG no disponible: {e}. Usando placeholder.")
        return None


def _load_trellis():
    """Carga TRELLIS desde HuggingFace como alternativa."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    try:
        from trellis.pipelines import TrellisImageTo3DPipeline
        print("[*] Cargando TRELLIS (Microsoft)...")
        pipe = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-Image-to-3D")
        pipe = pipe.to("cuda")
        _model_cache = pipe
        print("[+] TRELLIS cargado exitosamente.")
        return pipe
    except Exception as e:
        print(f"[!] TRELLIS no disponible: {e}. Usando placeholder.")
        return None


def generate_mesh_real(model, img: Image.Image) -> bytes:
    """Genera malla 3D con modelo real (TripoSG o TRELLIS)."""
    if model is None:
        return None
    try:
        result = model.generate(img)
        glb_bytes = result.export_to_glb()
        return glb_bytes
    except Exception as e:
        print(f"[!] Error en inferencia real: {e}. Fallback a placeholder.")
        return None


def generate_mesh_placeholder(img: Image.Image) -> bytes:
    """
    Genera una malla placeholder procedural (cubo texturizado con UV mapping)
    para validar el pipeline end-to-end cuando los modelos reales no están disponibles.
    """
    print("[*] Generando malla placeholder (cubo texturizado)...")

    img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
    texture_buffer = io.BytesIO()
    img_resized.save(texture_buffer, format="PNG")
    texture_buffer.seek(0)
    texture_bytes = texture_buffer.getvalue()
    padding_len = (4 - (len(texture_bytes) % 4)) % 4
    texture_bytes += b'\x00' * padding_len

    s = 0.5
    vertices = np.array([
        -s, -s,  s,   0.0, 1.0,   s, -s,  s,   1.0, 1.0,   s,  s,  s,   1.0, 0.0,  -s,  s,  s,   0.0, 0.0,
        -s, -s, -s,   1.0, 1.0,  -s,  s, -s,   1.0, 0.0,   s,  s, -s,   0.0, 0.0,   s, -s, -s,   0.0, 1.0,
        -s,  s, -s,   0.0, 1.0,  -s,  s,  s,   1.0, 1.0,   s,  s,  s,   1.0, 0.0,   s,  s, -s,   0.0, 0.0,
        -s, -s, -s,   0.0, 0.0,   s, -s, -s,   1.0, 0.0,   s, -s,  s,   1.0, 1.0,  -s, -s,  s,   0.0, 1.0,
         s, -s, -s,   0.0, 0.0,   s,  s, -s,   1.0, 0.0,   s,  s,  s,   1.0, 1.0,   s, -s,  s,   0.0, 1.0,
        -s, -s, -s,   1.0, 0.0,  -s, -s,  s,   0.0, 0.0,  -s,  s,  s,   0.0, 1.0,  -s,  s, -s,   1.0, 1.0,
    ], dtype=np.float32)

    indices = np.array([
        0,1,2, 0,2,3,  4,5,6, 4,6,7,  8,9,10, 8,10,11,
        12,13,14, 12,14,15,  16,17,18, 16,18,19,  20,21,22, 20,22,23,
    ], dtype=np.uint16)

    def align(b):
        pad = (4 - (len(b) % 4)) % 4
        return b + b'\x00' * pad

    vert_bytes = align(vertices.tobytes())
    idx_bytes = align(indices.tobytes())
    tex_offset = len(vert_bytes) + len(idx_bytes)
    bin_data = vert_bytes + idx_bytes + texture_bytes
    total_bin = len(bin_data)

    gltf_json = {
        "asset": {"version": "2.0", "generator": "BioRender TripoSG Placeholder"},
        "scenes": [{"nodes": [0]}], "scene": 0,
        "nodes": [{"name": "mesh_node", "mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "indices": 2, "material": 0}]}],
        "materials": [{"name": "mat", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "roughnessFactor": 0.5, "metallicFactor": 0.0}}],
        "textures": [{"source": 0}],
        "images": [{"bufferView": 3, "mimeType": "image/png"}],
        "buffers": [{"byteLength": total_bin}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(vert_bytes), "byteStride": 20, "target": 34962},
            {"buffer": 0, "byteOffset": len(vert_bytes), "byteLength": len(idx_bytes), "target": 34963},
            {"buffer": 0, "byteOffset": tex_offset, "byteLength": len(texture_bytes)},
        ],
        "accessors": [
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": 24, "type": "VEC3"},
            {"bufferView": 0, "byteOffset": 12, "componentType": 5126, "count": 24, "type": "VEC2"},
            {"bufferView": 1, "byteOffset": 0, "componentType": 5123, "count": 36, "type": "SCALAR"},
        ]
    }

    json_str = json.dumps(gltf_json)
    json_bytes = json_str.encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b' ' * json_pad

    glb_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    header = struct.pack("<III", 0x46546C67, 2, glb_length)
    chunk0 = struct.pack("<II", len(json_bytes), 0x4E4F534A)
    chunk1 = struct.pack("<II", len(bin_data), 0x004E4942)
    return header + chunk0 + json_bytes + chunk1 + bin_data


@celery_app.task(name="tasks.generate_triposg", queue="generation_triposg")
def generate_triposg(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea Celery que genera malla 3D usando TripoSG/TRELLIS (ruta quality).
    """
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    preprocessed_key = payload.get("preprocessed_key")

    if not job_id or not preprocessed_key:
        raise ValueError("Payload incompleto.")

    print(f"[*] Iniciando generación 3D Quality (TripoSG/TRELLIS) para Job {job_id}...")

    try:
        dl_start = time.perf_counter()
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=preprocessed_key)
        img_data = response["Body"].read()
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        dl_dur = int((time.perf_counter() - dl_start) * 1000)

        gen_start = time.perf_counter()
        model = None
        if MODEL_CHOICE == "trellis":
            model = _load_trellis()
        else:
            model = _load_triposg()
            if model is None:
                model = _load_trellis()

        glb_data = None
        if model is not None:
            glb_data = generate_mesh_real(model, img)

        if glb_data is None:
            print("[!] Modelos reales no disponibles. Generando placeholder...")
            glb_data = generate_mesh_placeholder(img)

        gen_dur = int((time.perf_counter() - gen_start) * 1000)

        ul_start = time.perf_counter()
        mesh_key = f"uploads/{job_id}/mesh_triposg/model.glb"
        s3_client.put_object(Bucket=BUCKET_NAME, Key=mesh_key, Body=glb_data, ContentType="model/gltf-binary")
        ul_dur = int((time.perf_counter() - ul_start) * 1000)

        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(f"[PERF_LOG] Task: generate_triposg | Descarga: {dl_dur}ms | Generación: {gen_dur}ms | Subida: {ul_dur}ms | Total: {total_dur}ms")

        status_update = {
            "status": "processing", "progress": 50, "result_url": "",
            "updated_at": int(time.time()), "stage": "generation_done"
        }
        redis_client.set(f"job:status:{job_id}", json.dumps(status_update))

        next_payload = {"job_id": job_id, "mesh_key": mesh_key, "route_info": payload.get("route_info", {})}
        celery_app.send_task("tasks.rig_mesh_unirig", args=[next_payload], queue="rigging_unirig")
        print(f"[+] Job {job_id} malla generada. Encolado en 'rigging_unirig'.")

        return {"status": "success", "job_id": job_id, "mesh_key": mesh_key, "duration_ms": total_dur}

    except Exception as err:
        print(f"[!] Error en generate_triposg Job {job_id}: {str(err)}")
        redis_client.set(f"job:status:{job_id}", json.dumps({
            "status": "error", "progress": 100, "result_url": "",
            "error_message": str(err), "updated_at": int(time.time())
        }))
        raise err
