"""
Archivo: render_script.py
Fecha de modificación: 31/05/2026
Autor: Alex Prieto

Descripción:
Script de automatización para Blender Headless (ejecutado mediante Blender Python API `bpy`).
Limpia la escena inicial, carga el avatar en formato GLB (Pipeline A) y los datos de
movimiento continuo en formato BVH (MS 4.1). Crea dinámicamente restricciones de
retargeting cinemático (Copy Rotation) para asociar las rotaciones de los joints del
esqueleto del BVH a los huesos del avatar, configura una cámara orbital interactiva,
luces dinámicas de tres puntos y el motor Eevee para renderizar frame a frame la
secuencia final en un archivo de video codificado en H.264 MP4.

Sustentación Científica:
El renderizado asíncrono y headless sobre contenedores usando Eevee (Blender Engine)
posibilita el horneado distribuido de cinemáticas complejas sin ocupar recursos de la
pantalla del servidor o cliente, logrando fotorrealismo en tiempos de render óptimos.

Acciones Principales:
    - Inicializar y limpiar la escena 3D predeterminada de Blender.
    - Cargar el modelo del personaje .glb y el esqueleto animado .bvh.
    - Crear y enlazar restricciones 'COPY_ROTATION' entre el armature de destino y origen.
    - Configurar cámaras, luces difusas de fondo y set-up de composición de escena.
    - Establecer motor de renderizado a EEVEE y salida de codificación FFmpeg (MP4 H.264).
    - Ejecutar el renderizado y exportar al directorio de outputs.

Entradas / Dependencias:
    - Entorno de ejecución Blender Headless con Python incorporado (bpy).
    - Ruta al archivo GLB y BVH pasados por argumentos de línea.

Salidas / Efectos:
    - Archivo de video final 'final_video.mp4' escrito en disco local listo para subir.

Ejecución:
    blender --background --python render_script.py -- <avatar.glb> <motion.bvh> <output.mp4>
"""

import json
import os
import sys
import bpy


def clean_scene() -> None:
    """
    Limpia todos los objetos preexistentes (cubo, cámara, lámpara) en la escena de Blender.
    """
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def load_gltf_avatar(glb_path: str) -> bpy.types.Object:
    """
    Importa el modelo del personaje GLB en la escena.

    Args:
        glb_path (str): Ruta local al archivo GLB.

    Returns:
        bpy.types.Object: El objeto Armature (esqueleto) importado.
    """
    bpy.ops.import_scene.gltf(filepath=glb_path)
    
    # Encontrar y retornar el Armature del avatar
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE" and "hips" in obj.pose.bones:
            return obj
            
    # Si no se encuentra hips, retornar el primer armature
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
            
    raise ValueError("No se encontro un Armature valido en el archivo GLB.")


def load_bvh_animation(bvh_path: str) -> bpy.types.Object:
    """
    Importa la animación BVH en la escena de Blender.

    Args:
        bvh_path (str): Ruta local al archivo BVH.

    Returns:
        bpy.types.Object: Objeto Armature de la animación importada.
    """
    bpy.ops.import_anim.bvh(filepath=bvh_path, filter_glob="*.bvh", target_space="GLOBAL")
    
    # El importador de BVH selecciona automáticamente el esqueleto importado
    bvh_armature = bpy.context.active_object
    if bvh_armature and bvh_armature.type == "ARMATURE":
        return bvh_armature
        
    raise ValueError("Fallo al importar el archivo BVH.")


def apply_retargeting(target_armature: bpy.types.Object, source_armature: bpy.types.Object) -> None:
    """
    Aplica restricciones de retargeting cinemático copiando rotaciones de huesos.

    Args:
        target_armature (bpy.types.Object): Armature del avatar GLB (destino).
        source_armature (bpy.types.Object): Armature de la animación BVH (origen).
    """
    # Mapeo estándar de huesos correspondientes
    bone_mapping = {
        "hips": "hips",
        "spine": "spine",
        "neck": "neck",
        "head": "head",
        "left_shoulder": "left_shoulder",
        "left_arm": "left_arm",
        "left_forearm": "left_forearm",
        "right_shoulder": "right_shoulder",
        "right_arm": "right_arm",
        "right_forearm": "right_forearm",
        "left_hip": "left_hip",
        "left_up_leg": "left_up_leg",
        "left_leg": "left_leg",
        "right_hip": "right_hip",
        "right_up_leg": "right_up_leg",
        "right_leg": "right_leg"
    }
    
    # Activar el armature del avatar de destino
    bpy.context.view_layer.objects.active = target_armature
    bpy.ops.object.mode_set(mode="POSE")
    
    for target_name, source_name in bone_mapping.items():
        if target_name in target_armature.pose.bones and source_name in source_armature.pose.bones:
            bone = target_armature.pose.bones[target_name]
            
            # Crear restricción COPY_ROTATION
            constraint = bone.constraints.new(type="COPY_ROTATION")
            constraint.target = source_armature
            constraint.subtarget = source_name
            constraint.target_space = "POSE"
            constraint.owner_space = "POSE"
            
    # Volver a modo objeto
    bpy.ops.object.mode_set(mode="OBJECT")


def setup_lighting_and_camera() -> None:
    """
    Configura luces dinámicas de tres puntos y la cámara orbital en la escena.
    """
    # 1. Configurar Cámara
    bpy.ops.object.camera_add(location=(0.0, -3.0, 1.0), rotation=(1.45, 0.0, 0.0))
    camera = bpy.context.active_object
    bpy.context.scene.camera = camera
    
    # 2. Luz Principal (Key Light)
    bpy.ops.object.light_add(type="SUN", location=(3.0, -3.0, 5.0))
    key_light = bpy.context.active_object
    key_light.data.energy = 3.0
    
    # 3. Luz de Relleno (Fill Light)
    bpy.ops.object.light_add(type="POINT", location=(-3.0, -2.0, 3.0))
    fill_light = bpy.context.active_object
    fill_light.data.energy = 50.0
    
    # 4. Luz de Contorno (Rim Light)
    bpy.ops.object.light_add(type="POINT", location=(0.0, 4.0, 2.0))
    rim_light = bpy.context.active_object
    rim_light.data.energy = 80.0


def configure_render_engine(output_path: str) -> None:
    """
    Configura el motor de renderizado Eevee y la compresión FFmpeg H.264.

    Args:
        output_path (str): Ruta absoluta local para exportar el MP4.
    """
    scene = bpy.context.scene
    
    # Establecer motor a EEVEE
    scene.render.engine = "BLENDER_EEVEE"
    
    # Resolución Full HD
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    
    # Configurar formato de salida a video FFmpeg
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    
    # Tasa de frames a 30 FPS
    scene.render.fps = 30
    
    # Ruta de salida sin extensión (.mp4 se añade automáticamente)
    base_path, _ = os.path.splitext(output_path)
    scene.render.filepath = base_path


def main() -> None:
    """
    Punto de entrada principal para la inicialización y ejecución del script en Blender.
    """
    # Los argumentos pasados después de '--' en la consola se leen de sys.argv
    try:
        args_idx = sys.argv.index("--")
        custom_args = sys.argv[args_idx + 1:]
    except ValueError:
        print("[!] Error: Debes pasar los argumentos usando '--' en la terminal.")
        sys.exit(1)
        
    if len(custom_args) < 3:
        print("[!] Uso: blender -b -P render_script.py -- <avatar.glb> <motion.bvh> <output.mp4>")
        sys.exit(1)
        
    glb_path = custom_args[0]
    bvh_path = custom_args[1]
    output_path = custom_args[2]
    
    print(f"[*] Limpiando escena 3D...")
    clean_scene()
    
    print(f"[*] Importando avatar GLB desde: {glb_path}...")
    avatar = load_gltf_avatar(glb_path)
    
    print(f"[*] Importando animación esquelética BVH desde: {bvh_path}...")
    animation = load_bvh_animation(bvh_path)
    
    print(f"[*] Aplicando restricciones de retargeting (Copy Rotation)...")
    apply_retargeting(avatar, animation)
    
    print(f"[*] Creando camaras e iluminación...")
    setup_lighting_and_camera()
    
    # Ajustar frames de animación de la escena según el BVH
    if animation.animation_data and animation.animation_data.action:
        frame_range = animation.animation_data.action.frame_range
        bpy.context.scene.frame_start = int(frame_range[0])
        bpy.context.scene.frame_end = int(frame_range[1])
        print(f"[*] Rango de animacion detectado: {bpy.context.scene.frame_start} a {bpy.context.scene.frame_end}")
    else:
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = 150
        
    print(f"[*] Configurando motor de renderizado Eevee y codificación...")
    configure_render_engine(output_path)
    
    print(f"[*] Iniciando renderizado de video headless...")
    bpy.ops.render.render(animation=True)
    print(f"[+] Renderizado offline finalizado exitosamente. Guardado en: {output_path}")


if __name__ == "__main__":
    main()
