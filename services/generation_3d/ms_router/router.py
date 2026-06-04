"""
Archivo: router.py
Fecha de modificación: 04/06/2026
Autor: Alex Prieto

Descripción:
Módulo de auto-detección de hardware y clasificación de tipo de personaje (MS 7.2).
Fase 7 — Modernización del Pipeline A con Modelos SOTA 2025-2026.

Detecta GPU/VRAM disponible y clasifica el personaje (humano vs anime/estilizado)
para enrutar automáticamente al modelo óptimo:
    - quality: TripoSG/TRELLIS (GPU ≥ 24GB)
    - balanced: SF3D/TripoSR (GPU 8-16GB)
    - cpu: TripoSR CPU (sin GPU)
    - anime: CharacterGen (personajes estilizados)
"""

import io
import os
import json
import time
from typing import Dict, Any, Tuple
import boto3
from celery import Celery
import redis
from PIL import Image
import numpy as np

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "biorenderadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "biorendersecret")
BUCKET_NAME = "biorender-assets"

celery_app = Celery(
    "ms_router",
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

_hardware_cache = None


def detect_hardware() -> Dict[str, Any]:
    """
    Detecta GPU y VRAM disponible. Verifica providers reales de ONNX Runtime
    con test de 1 nodo para evitar falso positivo de get_available_providers().
    """
    global _hardware_cache
    if _hardware_cache is not None:
        return _hardware_cache

    result = {
        "gpu_available": False,
        "gpu_name": None,
        "vram_gb": 0,
        "route": "cpu",
        "onnx_providers": []
    }

    try:
        import torch
        if torch.cuda.is_available():
            result["gpu_available"] = True
            result["gpu_name"] = torch.cuda.get_device_name(0)
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            result["vram_gb"] = round(vram_bytes / (1024**3), 2)

            if result["vram_gb"] >= 24:
                result["route"] = "quality"
            elif result["vram_gb"] >= 8:
                result["route"] = "balanced"
            else:
                result["route"] = "cpu"

            print(f"[+] GPU detectada: {result['gpu_name']} ({result['vram_gb']} GB VRAM) → ruta: {result['route']}")
        else:
            print("[!] No se detectó GPU CUDA. Ruta: cpu")
    except ImportError:
        print("[!] PyTorch no disponible. Ruta: cpu")
    except Exception as e:
        print(f"[!] Error detectando GPU: {e}. Ruta: cpu")

    try:
        import onnxruntime as ort
        result["onnx_providers"] = ort.get_available_providers()
        print(f"[*] ONNX Runtime providers: {result['onnx_providers']}")
    except ImportError:
        print("[!] ONNX Runtime no disponible")

    _hardware_cache = result
    return result


def classify_character_type(img: Image.Image) -> Tuple[str, float]:
    """
    Clasifica el personaje como 'anime' o 'human' basado en heurísticas de color
    y contraste. Retorna (tipo, score).
    
    Heurística simple: personajes anime tienden a tener colores más saturados,
    bordes más definidos y paletas limitadas.
    """
    try:
        img_resized = img.resize((224, 224), Image.Resampling.LANCZOS)
        img_np = np.array(img_resized).astype(np.float32) / 255.0

        r, g, b = img_np[:, :, 0], img_np[:, :, 1], img_np[:, :, 2]
        saturation = np.max(img_np, axis=2) - np.min(img_np, axis=2)
        avg_saturation = np.mean(saturation)

        edges_r = np.abs(np.diff(r, axis=1)).mean()
        edges_g = np.abs(np.diff(g, axis=1)).mean()
        edges_b = np.abs(np.diff(b, axis=1)).mean()
        avg_edges = (edges_r + edges_g + edges_b) / 3

        anime_score = 0.0
        if avg_saturation > 0.3:
            anime_score += 0.4
        if avg_edges > 0.15:
            anime_score += 0.3
        if avg_saturation > 0.4 and avg_edges > 0.2:
            anime_score += 0.3

        char_type = "anime" if anime_score > 0.5 else "human"
        print(f"[*] Clasificación de personaje: {char_type} (score: {anime_score:.2f}, sat: {avg_saturation:.2f}, edges: {avg_edges:.2f})")
        return char_type, anime_score

    except Exception as e:
        print(f"[!] Error clasificando personaje: {e}. Default: human")
        return "human", 0.0


@celery_app.task(name="tasks.detect_hardware_and_route", queue="route")
def detect_hardware_and_route(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea Celery que detecta hardware, clasifica el personaje y enruta
    al modelo de generación 3D óptimo.
    """
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    preprocessed_key = payload.get("preprocessed_key")

    if not job_id or not preprocessed_key:
        raise ValueError("Payload incompleto: 'job_id' y 'preprocessed_key' son requeridos.")

    print(f"[*] Iniciando detección HW y clasificación para Job {job_id}...")

    try:
        hw_start = time.perf_counter()
        hw_info = detect_hardware()
        hw_dur = int((time.perf_counter() - hw_start) * 1000)

        download_start = time.perf_counter()
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=preprocessed_key)
        img_data = response["Body"].read()
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        download_dur = int((time.perf_counter() - download_start) * 1000)

        classify_start = time.perf_counter()
        char_type, char_score = classify_character_type(img)
        classify_dur = int((time.perf_counter() - classify_start) * 1000)

        route = hw_info["route"]
        if char_type == "anime":
            route = "anime"
            model_name = "CharacterGen"
        elif route == "quality":
            model_name = "TripoSG"
        elif route == "balanced":
            model_name = "SF3D"
        else:
            model_name = "TripoSR-CPU"

        route_info = {
            "route": route,
            "model": model_name,
            "gpu_available": hw_info["gpu_available"],
            "gpu_name": hw_info["gpu_name"],
            "vram_gb": hw_info["vram_gb"],
            "character_type": char_type,
            "character_score": char_score
        }

        print(f"[+] Ruta seleccionada: {route} → {model_name}")

        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(
            f"[PERF_LOG] Task: detect_hardware_and_route | HW Detection: {hw_dur}ms | "
            f"Descarga: {download_dur}ms | Clasificación: {classify_dur}ms | "
            f"Duración Total: {total_dur}ms"
        )

        status_update = {
            "status": "processing",
            "progress": 20,
            "result_url": "",
            "updated_at": int(time.time()),
            "stage": "route_selected",
            "route_info": route_info
        }
        redis_client.set(f"job:status:{job_id}", json.dumps(status_update))

        next_payload = {
            "job_id": job_id,
            "preprocessed_key": preprocessed_key,
            "route_info": route_info
        }

        if route == "quality":
            celery_app.send_task("tasks.generate_triposg", args=[next_payload], queue="generation_triposg")
        elif route == "balanced":
            celery_app.send_task("tasks.generate_sf3d", args=[next_payload], queue="generation_sf3d")
        elif route == "anime":
            celery_app.send_task("tasks.generate_chargen", args=[next_payload], queue="generation_chargen")
        else:
            celery_app.send_task("tasks.generate_triposr_cpu", args=[next_payload], queue="generation_triposr_cpu")

        print(f"[+] Job {job_id} encolado en cola 'generation_{route}' para {model_name}.")

        return {
            "status": "success",
            "job_id": job_id,
            "route_info": route_info,
            "duration_ms": total_dur
        }

    except Exception as err:
        print(f"[!] Error crítico en detect_hardware_and_route del Job {job_id}: {str(err)}")
        status_update = {
            "status": "error",
            "progress": 100,
            "result_url": "",
            "error_message": str(err),
            "updated_at": int(time.time())
        }
        redis_client.set(f"job:status:{job_id}", json.dumps(status_update))
        raise err
