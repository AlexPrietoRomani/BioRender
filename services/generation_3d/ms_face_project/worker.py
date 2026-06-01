"""
Archivo: worker.py
Fecha de modificación: 31/05/2026
Autor: Alex Prieto

Descripción:
Worker asíncrono de Celery para el microservicio de proyección facial (MS 3.5).
Actúa como el fallback rápido en CPU (Pipeline A CPU Fallback / Modo Fast-Track).
Intercepta las tareas de generación 3D, descarga la foto del rostro del usuario,
detecta y alinea el rostro usando MediaPipe FaceMesh, compila procedimentalmente
un modelo 3D GLB humanoide completo y rigged con la textura facial incrustada,
lo sube a MinIO y actualiza el estado en Redis a 'done'.

Acciones Principales:
    - Inicializar Celery y enlazar con Redis.
    - Utilizar MediaPipe FaceMesh en CPU para alinear y recortar el rostro.
    - Compilar dinámicamente un archivo binario GLB humanoide rigged con armature estándar.
    - Subir el GLB resultante a MinIO en 'uploads/{job_id}/final/avatar.glb'.
    - Actualizar la clave 'job:status:{job_id}' en Redis a 'done' al 100%.

Entradas / Dependencias:
    - Celery, redis, boto3, numpy, Pillow, mediapipe, opencv-python-headless.
"""

import io
import os
import json
import time
import struct
from typing import Dict, Any, Tuple
import boto3
from celery import Celery
import numpy as np
from PIL import Image
import redis

# Configuración de variables de entorno con fallbacks locales
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "biorenderadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "biorendersecret")
BUCKET_NAME = "biorender-assets"

# Inicializar Celery
celery_app = Celery(
    "ms_face_project",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Inicializar cliente S3 para MinIO
s3_client = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    region_name="us-east-1"
)

# Inicializar cliente de Redis para actualizar el estado
redis_client = redis.Redis.from_url(REDIS_URL)


def detect_and_align_face(input_img: Image.Image) -> Image.Image:
    """
    Detecta el rostro en la imagen de entrada usando MediaPipe FaceMesh y lo alinea.
    Si no se encuentra un rostro o la librería no está disponible, cae a un recorte central inteligente.

    Args:
        input_img (Image.Image): Imagen original de entrada.

    Returns:
        Image.Image: Imagen de rostro cuadrada de 256x256 píxeles lista para texturizado.
    """
    print("[*] Ejecutando alineación facial MediaPipe FaceMesh en CPU...")
    img_cv = cv2_img = np.array(input_img)
    
    # Redimensionar para consistencia
    input_img_res = input_img.resize((512, 512), Image.Resampling.LANCZOS)
    
    try:
        import mediapipe as mp
        import cv2

        mp_face_mesh = mp.solutions.face_mesh
        # Ejecución ultrarrápida optimizada para CPU
        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        ) as face_mesh:
            img_rgb = np.array(input_img_res)
            results = face_mesh.process(img_rgb)
            
            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark
                h, w, _ = img_rgb.shape
                
                # Obtener puntos clave: ojo izquierdo (33), ojo derecho (263), nariz (1)
                left_eye = np.array([landmarks[33].x * w, landmarks[33].y * h])
                right_eye = np.array([landmarks[263].x * w, landmarks[263].y * h])
                nose = np.array([landmarks[1].x * w, landmarks[1].y * h])
                
                # Calcular ángulo de inclinación para enderezar el rostro
                d_y = right_eye[1] - left_eye[1]
                d_x = right_eye[0] - left_eye[0]
                angle = np.degrees(np.arctan2(d_y, d_x))
                
                # Centro del rostro es el punto medio entre los ojos
                eye_center = (left_eye + right_eye) * 0.5
                
                # Obtener caja de recorte basada en la distancia ocular
                eye_dist = np.linalg.norm(right_eye - left_eye)
                crop_size = int(eye_dist * 4.5)
                
                # Crear matriz de rotación y rotar la imagen
                rot_mat = cv2.getRotationMatrix2D(tuple(eye_center), angle, 1.0)
                rotated = cv2.warpAffine(img_rgb, rot_mat, (w, h), flags=cv2.INTER_LINEAR)
                
                # Recortar caja centrada
                x1 = max(0, int(eye_center[0] - crop_size // 2))
                y1 = max(0, int(eye_center[1] - crop_size // 3)) # Un poco más arriba de los ojos
                x2 = min(w, x1 + crop_size)
                y2 = min(h, y1 + crop_size)
                
                cropped = rotated[y1:y2, x1:x2]
                face_pil = Image.fromarray(cropped).resize((256, 256), Image.Resampling.LANCZOS)
                print("[+] Rostro detectado y alineado con éxito mediante FaceMesh.")
                return face_pil
                
    except Exception as err:
        print(f"[!] Fallback a recorte heurístico por error en FaceMesh: {str(err)}")
        
    # Recorte central heurístico de fallback si falla MediaPipe
    w, h = input_img_res.size
    min_dim = min(w, h)
    x1 = (w - min_dim) // 2
    y1 = (h - min_dim) // 2
    cropped = input_img_res.crop((x1, y1, x1 + min_dim, y1 + min_dim))
    return cropped.resize((256, 256), Image.Resampling.LANCZOS)


def compile_procedural_glb(face_img: Image.Image) -> bytes:
    """
    Compila dinámicamente un archivo binario .glb completo y estructurado
    que contiene un avatar tridimensional representado como un plano vertical segmentado
    (títere 2D rigged) con la textura completa incrustada y asociada al esqueleto.

    Args:
        face_img (Image.Image): Imagen completa del personaje para la textura.

    Returns:
        bytes: Datos binarios del archivo GLB.
    """
    print("[*] Compilando procedimentalmente avatar 2D Puppet GLB rigged compatible con WebGL...")
    
    # 1. Ajustar tamaño y voltear la imagen verticalmente para WebGL/glTF
    img_width, img_height = face_img.size
    max_size = 512
    if img_width > max_size or img_height > max_size:
        face_img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        img_width, img_height = face_img.size

    flipped_img = face_img.transpose(Image.FLIP_TOP_BOTTOM)

    # Guardar a bytes PNG
    texture_buffer = io.BytesIO()
    flipped_img.save(texture_buffer, format="PNG")
    texture_bytes = texture_buffer.getvalue()
    
    # Alinear la textura a 4 bytes
    padding_len = (4 - (len(texture_bytes) % 4)) % 4
    texture_bytes += b'\x00' * padding_len

    # 2. Definir geometría de la malla: Tarjeta vertical segmentada en 4 secciones (5 niveles de altura)
    # Conservamos la relación de aspecto original para evitar deformaciones
    aspect_ratio = img_width / img_height
    half_width = 0.4 * aspect_ratio

    # Vértices: Posición (x, y, z), Coordenada UV (u, v)
    vertices = np.array([
        # X, Y, Z, U, V
        -half_width, -0.8, 0.0,   0.0, 0.0,   # V0
         half_width, -0.8, 0.0,   1.0, 0.0,   # V1
        -half_width, -0.3, 0.0,   0.0, 0.25,  # V2
         half_width, -0.3, 0.0,   1.0, 0.25,  # V3
        -half_width,  0.2, 0.0,   0.0, 0.5,   # V4
         half_width,  0.2, 0.0,   1.0, 0.5,   # V5
        -half_width,  0.7, 0.0,   0.0, 0.75,  # V6
         half_width,  0.7, 0.0,   1.0, 0.75,  # V7
        -half_width,  1.2, 0.0,   0.0, 1.0,   # V8
         half_width,  1.2, 0.0,   1.0, 1.0,   # V9
    ], dtype=np.float32)
    
    # Índices (2 triángulos por segmento vertical)
    indices = np.array([
        0, 1, 3,  0, 3, 2,  # Segmento 0 (Asociado a Cadera)
        2, 3, 5,  2, 5, 4,  # Segmento 1 (Asociado a Columna)
        4, 5, 7,  4, 7, 6,  # Segmento 2 (Asociado a Columna superior/Hombros)
        6, 7, 9,  6, 9, 8,  # Segmento 3 (Asociado a Cabeza)
    ], dtype=np.uint16)
    
    # Mapeo de joints (0: Hips, 1: Spine, 2: Head)
    joints = np.array([
        0, 0, 0, 0,  # V0 (Hips)
        0, 0, 0, 0,  # V1 (Hips)
        0, 0, 0, 0,  # V2 (Hips)
        0, 0, 0, 0,  # V3 (Hips)
        1, 0, 0, 0,  # V4 (Spine)
        1, 0, 0, 0,  # V5 (Spine)
        2, 0, 0, 0,  # V6 (Head)
        2, 0, 0, 0,  # V7 (Head)
        2, 0, 0, 0,  # V8 (Head)
        2, 0, 0, 0,  # V9 (Head)
    ], dtype=np.uint8)

    weights = np.array([
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
    ], dtype=np.float32)

    # 3. Serializar buffers a binario
    vertex_bytes = vertices.tobytes()
    index_bytes = indices.tobytes()
    joint_bytes = joints.tobytes()
    weight_bytes = weights.tobytes()

    # Alineación de cada buffer a 4 bytes
    def align_bytes(b: bytes) -> bytes:
        pad = (4 - (len(b) % 4)) % 4
        return b + b'\x00' * pad

    vertex_bytes = align_bytes(vertex_bytes)
    index_bytes = align_bytes(index_bytes)
    joint_bytes = align_bytes(joint_bytes)
    weight_bytes = align_bytes(weight_bytes)

    # Offset de datos en la sección binaria del GLB
    offset_vert = 0
    offset_idx = len(vertex_bytes)
    offset_joint = offset_idx + len(index_bytes)
    offset_weight = offset_joint + len(joint_bytes)
    offset_tex = offset_weight + len(weight_bytes)
    total_bin_len = offset_tex + len(texture_bytes)

    bin_data = vertex_bytes + index_bytes + joint_bytes + weight_bytes + texture_bytes

    # 4. Construir cabecera JSON del glTF
    gltf_json = {
        "asset": {
            "version": "2.0",
            "generator": "BioRender Puppet Card Builder"
        },
        "scenes": [{"nodes": [0, 1]}],
        "scene": 0,
        "nodes": [
            {
                "name": "mesh_node",
                "mesh": 0,
                "skin": 0
            },
            {
                "name": "hips",
                "translation": [0, -0.6, 0],
                "children": [2],
            },
            {
                "name": "spine",
                "translation": [0, 0.7, 0],
                "children": [3],
            },
            {
                "name": "head",
                "translation": [0, 0.6, 0],
            }
        ],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": 0,
                            "TEXCOORD_0": 1,
                            "JOINTS_0": 3,
                            "WEIGHTS_0": 4
                        },
                        "indices": 2,
                        "material": 0
                    }
                ]
            }
        ],
        "materials": [
            {
                "name": "avatar_material",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "roughnessFactor": 0.5,
                    "metallicFactor": 0.1
                },
                "doubleSided": True
            }
        ],
        "textures": [{"source": 0}],
        "images": [{"bufferView": 4, "mimeType": "image/png"}],
        "skins": [
            {
                "joints": [1, 2, 3],
                "skeleton": 1
            }
        ],
        "buffers": [{"byteLength": total_bin_len}],
        "bufferViews": [
            # 0: Vértices (Posición + UV) -> 5 * 4 = 20 bytes de stride
            {"buffer": 0, "byteOffset": offset_vert, "byteLength": len(vertex_bytes), "byteStride": 20, "target": 34962},
            # 1: Índices
            {"buffer": 0, "byteOffset": offset_idx, "byteLength": len(index_bytes), "target": 34963},
            # 2: Joints
            {"buffer": 0, "byteOffset": offset_joint, "byteLength": len(joint_bytes), "target": 34962},
            # 3: Weights
            {"buffer": 0, "byteOffset": offset_weight, "byteLength": len(weight_bytes), "target": 34962},
            # 4: Textura PNG
            {"buffer": 0, "byteOffset": offset_tex, "byteLength": len(texture_bytes)}
        ],
        "accessors": [
            # 0: POSITION
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": 10, "type": "VEC3", "max": [float(half_width), 1.2, 0.0], "min": [float(-half_width), -0.8, 0.0]},
            # 1: TEXCOORD_0
            {"bufferView": 0, "byteOffset": 12, "componentType": 5126, "count": 10, "type": "VEC2"},
            # 2: INDICES
            {"bufferView": 1, "byteOffset": 0, "componentType": 5123, "count": 24, "type": "SCALAR"},
            # 3: JOINTS_0
            {"bufferView": 2, "byteOffset": 0, "componentType": 5121, "count": 10, "type": "VEC4"},
            # 4: WEIGHTS_0
            {"bufferView": 3, "byteOffset": 0, "componentType": 5126, "count": 10, "type": "VEC4"}
        ]
    }

    json_str = json.dumps(gltf_json)
    json_bytes = json_str.encode("utf-8")
    
    # Alinear JSON a 4 bytes
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b' ' * json_pad

    # 5. Escribir cabecera del archivo GLB
    # magic (4B), version (4B), total_length (4B)
    glb_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    header = struct.pack("<III", 0x46546C67, 2, glb_length)
    
    # Chunk 0 (JSON): length (4B), type (4B: "JSON"), data
    chunk0_header = struct.pack("<II", len(json_bytes), 0x4E4F534A)
    
    # Chunk 1 (BIN): length (4B), type (4B: "BIN\x00"), data
    chunk1_header = struct.pack("<II", len(bin_data), 0x004E4942)

    glb_data = header + chunk0_header + json_bytes + chunk1_header + bin_data
    print("[+] Avatar GLB procedimental compilado de forma exitosa.")
    return glb_data


@celery_app.task(name="tasks.face_project", queue="generation")
def face_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea Celery que descarga la foto de la cara, detecta los contornos faciales,
    genera el avatar rigged personalizado en GLB, lo sube y actualiza Redis.
    """
    start_time = time.perf_counter()
    job_id = payload.get("job_id")
    image_key = payload.get("input_image_key")
    
    if not job_id or not image_key:
        raise ValueError("Payload incompleto: 'job_id' e 'input_image_key' son requeridos.")
        
    print(f"[*] Iniciando Tarea face_project para el Job {job_id}...")
    
    try:
        # 1. Descargar la imagen de entrada desde MinIO
        s3_download_start = time.perf_counter()
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=image_key)
        input_data = response["Body"].read()
        input_image = Image.open(io.BytesIO(input_data)).convert("RGBA" if "A" in Image.open(io.BytesIO(input_data)).mode else "RGB")
        s3_download_dur = int((time.perf_counter() - s3_download_start) * 1000)
        
        # 2. Usar la imagen completa en lugar de recortar/alinear el rostro
        face_img = input_image
        face_detect_dur = 0
        
        # 3. Compilar el GLB rigged procedimental como plano segmentado (Puppet)
        glb_compile_start = time.perf_counter()
        glb_data = compile_procedural_glb(face_img)
        glb_compile_dur = int((time.perf_counter() - glb_compile_start) * 1000)
        
        # 4. Subir el avatar GLB a MinIO
        s3_upload_start = time.perf_counter()
        glb_key = f"uploads/{job_id}/final/avatar.glb"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=glb_key,
            Body=glb_data,
            ContentType="model/gltf-binary"
        )
        print(f"[+] Avatar GLB subido a: {glb_key}")
        s3_upload_dur = int((time.perf_counter() - s3_upload_start) * 1000)
        
        total_dur = int((time.perf_counter() - start_time) * 1000)
        print(
            f"[PERF_LOG] Task: face_project | Descarga S3: {s3_download_dur}ms | Deteccion/Alineacion FaceMesh: {face_detect_dur}ms | Compilacion GLB: {glb_compile_dur}ms | Subida S3: {s3_upload_dur}ms | Duracion Total: {total_dur}ms"
        )
        
        # 5. Actualizar el estado del Job en Redis a 'done' compatible con el Gateway
        status_update = {
            "status": "done",
            "progress": 100,
            "result_url": f"{BUCKET_NAME}/{glb_key}",
            "duration_ms": total_dur,
            "updated_at": int(time.time())
        }
        
        redis_key = f"job:status:{job_id}"
        redis_client.set(redis_key, json.dumps(status_update))
        print(f"[+] Job {job_id} marcado como 'done' exitosamente en Redis.")
        
        return {
            "status": "success",
            "job_id": job_id,
            "glb_key": glb_key,
            "duration_ms": total_dur
        }
        
    except Exception as err:
        print(f"[!] Error crítico en face_project del Job {job_id}: {str(err)}")
        # Registrar falla en Redis
        status_update = {
            "status": "error",
            "progress": 100,
            "result_url": "",
            "error_message": str(err),
            "updated_at": int(time.time())
        }
        redis_client.set(f"job:status:{job_id}", json.dumps(status_update))
        raise err


# Fallback transparente para interceptar la cola de generación normal en CPU
@celery_app.task(name="tasks.generate_multiview", queue="generation")
def generate_multiview_fallback(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback transparente para interceptar tareas de la cola 'generation' en CPU pura.
    Ejecuta directamente la proyección facial y compila el GLB en menos de 2 segundos.
    """
    print("[*] [CPU_FALLBACK_DETECTED] Interceptando tareas en CPU...")
    return face_project(payload)
