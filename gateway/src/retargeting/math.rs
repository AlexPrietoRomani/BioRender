//! Módulo: retargeting::math
//! Modificación: 2026-05-29
//! Autor: Alex Prieto
//!
//! Descripción:
//! Implementa los algoritmos cinemáticos locales en Rust usando la librería `glam`.
//! Convierte las coordenadas cartesianas de los landmarks obtenidos por MediaPipe a
//! rotaciones locales relativas representadas por cuaterniones unitarios para animar
//! el esqueleto jerárquico del avatar dummy.
//!
//! Estructura Interna:
//! - `get_keypoint_map(keypoints)`: Convierte la lista de landmarks en un mapa de vectores 3D corregidos.
//! - `calculate_retargeting(keypoints)`: Calcula el conjunto de rotaciones para cada articulación activa.
//!
//! Dependencias Principales:
//! - glam
//! - std::collections::HashMap

use std::collections::HashMap;
use glam::{Vec3, Quat};
use crate::models::ws_messages::{PythonKeypoint, BoneRotation};

/// Convierte la lista de keypoints planos provenientes del microservicio a un mapa indexado de vectores
/// en coordenadas 3D de mano derecha, invirtiendo el eje Y de la cámara.
///
/// # Argumentos
///
/// * `keypoints` - Arreglo de landmarks de pose retornados por Python.
fn get_keypoint_map(keypoints: &[PythonKeypoint]) -> HashMap<String, Vec3> {
    let mut map = HashMap::new();
    for kp in keypoints {
        // En MediaPipe, el eje Y va de arriba hacia abajo [0, 1]. Invertimos el eje Y para
        // mapear a un espacio 3D estándar donde Y apunta hacia arriba (ej: Three.js).
        let pos = Vec3::new(
            kp.x - 0.5,
            0.5 - kp.y, // +Y apunta hacia arriba
            -kp.z,      // Mantener profundidad z invertida
        );
        map.insert(kp.name.clone(), pos);
    }
    map
}

/// Calcula el retargeting de rotación para cada uno de los huesos principales del modelo humanoide.
///
/// Compara los vectores medidos reales con las direcciones de pose en T-Pose (reposo)
/// para deducir cuaterniones de rotación, aplicando multiplicaciones inversas para transformarlas
/// de coordenadas globales a locales en la jerarquía del armature.
///
/// # Argumentos
///
/// * `keypoints` - Arreglo de landmarks anatómicos medidos por MediaPipe.
///
/// # Ejemplo
///
/// ```
/// use crate::retargeting::math::calculate_retargeting;
/// let rotations = calculate_retargeting(&[]);
/// ```
pub fn calculate_retargeting(keypoints: &[PythonKeypoint]) -> Vec<BoneRotation> {
    let map = get_keypoint_map(keypoints);
    let mut rotations = Vec::new();

    // Obtener articulaciones clave
    let left_shoulder = map.get("left_shoulder").cloned();
    let left_elbow = map.get("left_elbow").cloned();
    let left_wrist = map.get("left_wrist").cloned();

    let right_shoulder = map.get("right_shoulder").cloned();
    let right_elbow = map.get("right_elbow").cloned();
    let right_wrist = map.get("right_wrist").cloned();

    let left_hip = map.get("left_hip").cloned();
    let right_hip = map.get("right_hip").cloned();

    // ── 1. Spine (Columna Central) ──
    if let (Some(l_shoulder), Some(r_shoulder), Some(l_hip), Some(r_hip)) = (left_shoulder, right_shoulder, left_hip, right_hip) {
        let shoulder_mid = (l_shoulder + r_shoulder) * 0.5;
        let hip_mid = (l_hip + r_hip) * 0.5;
        
        let dir = (shoulder_mid - hip_mid).try_normalize();
        if let Some(d) = dir {
            // Pose de descanso de Spine apunta verticalmente (+Y)
            let spine_rot = Quat::from_rotation_arc(Vec3::Y, d);
            rotations.push(BoneRotation {
                bone_name: "Spine".to_string(),
                quaternion: spine_rot.to_array(),
            });
        }
    }

    // ── 2. Brazo Izquierdo Superior (LeftUpperArm) ──
    let mut left_upper_arm_rot = Quat::IDENTITY;
    if let (Some(shoulder), Some(elbow)) = (left_shoulder, left_elbow) {
        let dir = (elbow - shoulder).try_normalize();
        if let Some(d) = dir {
            // Pose de descanso en T-Pose para el brazo izquierdo: apunta a la izquierda (-X)
            left_upper_arm_rot = Quat::from_rotation_arc(Vec3::new(-1.0, 0.0, 0.0), d);
            rotations.push(BoneRotation {
                bone_name: "LeftUpperArm".to_string(),
                quaternion: left_upper_arm_rot.to_array(),
            });
        }
    }

    // ── 3. Brazo Izquierdo Inferior / Antebrazo (LeftLowerArm) ──
    if let (Some(elbow), Some(wrist)) = (left_elbow, left_wrist) {
        let dir = (wrist - elbow).try_normalize();
        if let Some(d) = dir {
            // Pose de descanso: apunta a la izquierda (-X)
            let global_rot = Quat::from_rotation_arc(Vec3::new(-1.0, 0.0, 0.0), d);
            // Hacer la rotación local dividiendo por la rotación del padre (hombro)
            let local_rot = left_upper_arm_rot.inverse() * global_rot;
            rotations.push(BoneRotation {
                bone_name: "LeftLowerArm".to_string(),
                quaternion: local_rot.normalize().to_array(),
            });
        }
    }

    // ── 4. Brazo Derecho Superior (RightUpperArm) ──
    let mut right_upper_arm_rot = Quat::IDENTITY;
    if let (Some(shoulder), Some(elbow)) = (right_shoulder, right_elbow) {
        let dir = (elbow - shoulder).try_normalize();
        if let Some(d) = dir {
            // Pose de descanso en T-Pose para el brazo derecho: apunta a la derecha (+X)
            right_upper_arm_rot = Quat::from_rotation_arc(Vec3::new(1.0, 0.0, 0.0), d);
            rotations.push(BoneRotation {
                bone_name: "RightUpperArm".to_string(),
                quaternion: right_upper_arm_rot.to_array(),
            });
        }
    }

    // ── 5. Brazo Derecho Inferior / Antebrazo (RightLowerArm) ──
    if let (Some(elbow), Some(wrist)) = (right_elbow, right_wrist) {
        let dir = (wrist - elbow).try_normalize();
        if let Some(d) = dir {
            // Pose de descanso: apunta a la derecha (+X)
            let global_rot = Quat::from_rotation_arc(Vec3::new(1.0, 0.0, 0.0), d);
            // Hacer la rotación local dividiendo por la rotación del padre (hombro)
            let local_rot = right_upper_arm_rot.inverse() * global_rot;
            rotations.push(BoneRotation {
                bone_name: "RightLowerArm".to_string(),
                quaternion: local_rot.normalize().to_array(),
            });
        }
    }

    rotations
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_left_arm_horizontal_identity() {
        // Si el brazo izquierdo está horizontal de hombro a codo, debe coincidir
        // con la T-Pose, resultando en un cuaternión cercano a la identidad.
        let keypoints = vec![
            PythonKeypoint { name: "left_shoulder".to_string(), x: 0.5, y: 0.5, z: 0.0, visibility: 0.99 },
            PythonKeypoint { name: "left_elbow".to_string(), x: 0.2, y: 0.5, z: 0.0, visibility: 0.99 },
        ];

        let results = calculate_retargeting(&keypoints);
        let arm_rot = results.iter().find(|r| r.bone_name == "LeftUpperArm").unwrap();
        
        // Quat identidad es [0, 0, 0, 1]
        assert!((arm_rot.quaternion[0]).abs() < 0.001);
        assert!((arm_rot.quaternion[1]).abs() < 0.001);
        assert!((arm_rot.quaternion[2]).abs() < 0.001);
        assert!((arm_rot.quaternion[3] - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_calculate_left_arm_vertical_90_degrees() {
        // Si el codo izquierdo se levanta a 90 grados apuntando verticalmente hacia arriba
        // (+Y en espacio transformado), se calcula la rotación respecto al eje -X.
        // Hombro en (0.5, 0.5, 0.0) -> (0.0, 0.0, 0.0) 3D
        // Codo en (0.5, 0.2, 0.0) -> (0.0, 0.3, 0.0) 3D (eje Y positivo hacia arriba)
        let keypoints = vec![
            PythonKeypoint { name: "left_shoulder".to_string(), x: 0.5, y: 0.5, z: 0.0, visibility: 0.99 },
            PythonKeypoint { name: "left_elbow".to_string(), x: 0.5, y: 0.2, z: 0.0, visibility: 0.99 },
        ];

        let results = calculate_retargeting(&keypoints);
        let arm_rot = results.iter().find(|r| r.bone_name == "LeftUpperArm").unwrap();
        
        // Rotación de 90 grados en el eje Z (con eje de rotación [0, 0, -1] dado el producto cruz): [0, 0, -sin(45°), cos(45°)] = [0, 0, -0.7071, 0.7071]
        assert!((arm_rot.quaternion[0]).abs() < 0.001);
        assert!((arm_rot.quaternion[1]).abs() < 0.001);
        assert!((arm_rot.quaternion[2] - -0.7071).abs() < 0.001);
        assert!((arm_rot.quaternion[3] - 0.7071).abs() < 0.001);
    }
}
