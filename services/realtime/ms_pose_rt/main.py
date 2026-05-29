"""
Archivo: main.py
Modificación: 2026-05-29
Autor: Alex Prieto

Descripción:
Punto de entrada del microservicio de detección de pose humana en tiempo real.
Expone una API asíncrona mediante FastAPI y ejecuta inferencia en CPU utilizando
el motor ligero de landmarks de MediaPipe Pose. Recibe imágenes en base64,
las decodifica con OpenCV, ejecuta la estimación de la pose humana y retorna los
landmarks tridimensionales detectados.

Acciones Principales:
    - Decodificar imágenes base64 a matrices NumPy mediante OpenCV.
    - Ejecutar inferencia de landmarks de pose en tiempo real con MediaPipe Pose.
    - Exponer endpoints HTTP asíncronos para salud e inferencia de poses.

Estructura Interna:
    - `FrameInput`: Pydantic model para los datos del frame entrante.
    - `Keypoint`: Pydantic model para un landmark de articulación.
    - `PoseOutput`: Pydantic model para las articulaciones detectadas y confianza global.
    - `decode_base64_image(base64_str)`: Decodifica un string base64 a imagen OpenCV.
    - `detect_pose(frame)`: Endpoint POST para la detección del esqueleto.

Entradas / Dependencias:
    - FastAPI, OpenCV, MediaPipe, NumPy, Pydantic.

Salidas / Efectos:
    - Retorna JSON estructurado con coordenadas espaciales tridimensionales de las articulaciones.

Integración UI:
    - Este archivo expone el endpoint `/detect-pose` invocado por el Gateway de Rust.
"""

import base64
from typing import List, Dict, Any
import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

# Inicialización de la aplicación FastAPI con fines de documentación
app = FastAPI(
    title="BioRender Pose Detection RT API",
    description="Microservicio liviano para detección de landmarks corporales en tiempo real.",
    version="0.1.0"
)

# Inicializar componentes de MediaPipe para Pose
mp_pose = mp.solutions.pose
pose_estimator = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=0,  # Priorizar el rendimiento en CPU (latencia mínima)
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Mapeo oficial de los 33 landmarks corporales de MediaPipe
LANDMARK_NAMES: Dict[int, str] = {
    0: "nose", 1: "left_eye_inner", 2: "left_eye", 3: "left_eye_outer",
    4: "right_eye_inner", 5: "right_eye", 6: "right_eye_outer",
    7: "left_ear", 8: "right_ear", 9: "mouth_left", 10: "mouth_right",
    11: "left_shoulder", 12: "right_shoulder", 13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist", 17: "left_pinky", 18: "right_pinky",
    19: "left_index", 20: "right_index", 21: "left_thumb", 22: "right_thumb",
    23: "left_hip", 24: "right_hip", 25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle", 29: "left_heel", 30: "right_heel",
    31: "left_foot_index", 32: "right_foot_index"
}


class FrameInput(BaseModel):
    frame_data: str = Field(..., description="Imagen del frame codificada en JPEG Base64.")
    frame_id: int = Field(..., description="Identificador secuencial del frame.")


class Keypoint(BaseModel):
    name: str = Field(..., description="Nombre identificativo de la articulación.")
    x: float = Field(..., description="Coordenada X normalizada [0.0, 1.0].")
    y: float = Field(..., description="Coordenada Y normalizada [0.0, 1.0].")
    z: float = Field(..., description="Coordenada Z normalizada / escala de profundidad.")
    visibility: float = Field(..., description="Confianza o visibilidad de la estimación.")


class PoseOutput(BaseModel):
    frame_id: int = Field(..., description="ID del frame procesado.")
    keypoints: List[Keypoint] = Field(default=[], description="Lista de landmarks detectados.")
    confidence: float = Field(default=0.0, description="Confianza global promedio.")


def decode_base64_image(base64_str: str) -> np.ndarray:
    """
    Decodifica una imagen binaria JPEG codificada en Base64.

    Args:
        base64_str (str): Cadena de texto base64, que puede incluir el prefijo data URI.

    Returns:
        np.ndarray: Matriz de imagen OpenCV (BGR).

    Raises:
        ValueError: Si la cadena no es decodificable o es inválida.
    """
    try:
        # Remover prefijos de tipo "data:image/jpeg;base64," si están presentes
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        
        image_bytes = base64.b64decode(base64_str)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("La imagen decodificada es nula.")
        return image
    except Exception as e:
        raise ValueError(f"Error al decodificar la cadena Base64: {str(e)}")


@app.get("/health")
async def health() -> Dict[str, str]:
    """
    Endpoint para validación de salud (sanity check).

    Returns:
        dict: Estado del microservicio.
    """
    return {"status": "ok", "service": "pose_detection_rt"}


@app.post("/detect-pose", response_model=PoseOutput, status_code=status.HTTP_200_OK)
async def detect_pose(payload: FrameInput) -> PoseOutput:
    """
    Procesa un frame codificado en base64 para estimar las landmarks anatómicas.

    Args:
        payload (FrameInput): Objeto con los datos del frame y su ID secuencial.

    Returns:
        PoseOutput: Landmarks detectados y confianza global.
    """
    try:
        # Decodificar el frame base64
        image_bgr = decode_base64_image(payload.frame_data)
        
        # Convertir a RGB para que MediaPipe pueda procesarlo correctamente
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        
        # Ejecutar inferencia en CPU
        results = pose_estimator.process(image_rgb)
        
        keypoints_list: List[Keypoint] = []
        global_confidence = 0.0
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            total_visibility = 0.0
            
            for idx, lm in enumerate(landmarks):
                name = LANDMARK_NAMES.get(idx, f"landmark_{idx}")
                keypoints_list.append(
                    Keypoint(
                        name=name,
                        x=float(lm.x),
                        y=float(lm.y),
                        z=float(lm.z),
                        visibility=float(lm.visibility)
                    )
                )
                total_visibility += lm.visibility
                
            global_confidence = total_visibility / len(landmarks) if landmarks else 0.0
            
        return PoseOutput(
            frame_id=payload.frame_id,
            keypoints=keypoints_list,
            confidence=global_confidence
        )
        
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falla interna en la estimación de la pose: {str(err)}"
        )
