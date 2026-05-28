"""
Archivo: main.py
Modificación: 2026-05-28
Autor: Alex Prieto

Descripción:
Punto de entrada del microservicio de detección de pose humana en tiempo real.
Expone una API asíncrona mediante FastAPI y ejecuta inferencia en CPU utilizando
el motor ligero de landmarks de MediaPipe Pose.

Integración UI:
    - Este archivo expone el endpoint `/detect-pose` invocado por el Gateway de Rust.
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="BioRender Pose Detection RT API",
    description="Microservicio liviano para detección de landmarks corporales en tiempo real.",
    version="0.1.0"
)

class FrameInput(BaseModel):
    frame_data: str = Field(..., description="Imagen del frame codificada en JPEG Base64.")
    frame_id: int = Field(..., description="Identificador secuencial del frame.")

class Keypoint(BaseModel):
    name: str = Field(..., description="Nombre identificativo de la articulación.")
    x: float = Field(..., description="Coordenada X normalizada.")
    y: float = Field(..., description="Coordenada Y normalizada.")
    z: float = Field(..., description="Coordenada Z normalizada.")
    visibility: float = Field(..., description="Confianza o visibilidad de la estimación.")

class PoseOutput(BaseModel):
    frame_id: int = Field(..., description="ID del frame procesado.")
    keypoints: list[Keypoint] = Field(default=[], description="Lista de landmarks detectados.")
    confidence: float = Field(default=0.0, description="Confianza global promedio.")

@app.get("/health")
async def health() -> dict[str, str]:
    """
    Endpoint para validación de salud (sanity check).

    Returns:
        dict: Estado del microservicio.
    """
    return {"status": "ok", "service": "pose_detection_rt"}
