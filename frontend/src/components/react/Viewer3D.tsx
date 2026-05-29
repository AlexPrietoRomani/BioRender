import React, { useRef, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { BoneRotation } from '../../hooks/useWebSocket';

interface Viewer3DProps {
  /**
   * Colección de rotaciones de hueso calculadas en el Gateway.
   */
  boneRotations: BoneRotation[];
}

/**
 * Componente que representa el esqueleto del avatar humanoid.
 * Maneja la jerarquía anatómica y aplica reactivamente los cuaterniones de rotación.
 */
const HumanoidSkeleton: React.FC<{ boneRotations: BoneRotation[] }> = ({ boneRotations }) => {
  const spineRef = useRef<THREE.Group>(null);
  const leftUpperArmRef = useRef<THREE.Group>(null);
  const leftLowerArmRef = useRef<THREE.Group>(null);
  const rightUpperArmRef = useRef<THREE.Group>(null);
  const rightLowerArmRef = useRef<THREE.Group>(null);

  useEffect(() => {
    if (!boneRotations || boneRotations.length === 0) return;

    // Aplicar las rotaciones de hueso sobre las referencias de pivote de Three.js
    boneRotations.forEach((rot) => {
      const q = new THREE.Quaternion(
        rot.quaternion[0],
        rot.quaternion[1],
        rot.quaternion[2],
        rot.quaternion[3]
      );

      switch (rot.bone_name) {
        case 'Spine':
          if (spineRef.current) spineRef.current.quaternion.copy(q);
          break;
        case 'LeftUpperArm':
          if (leftUpperArmRef.current) leftUpperArmRef.current.quaternion.copy(q);
          break;
        case 'LeftLowerArm':
          if (leftLowerArmRef.current) leftLowerArmRef.current.quaternion.copy(q);
          break;
        case 'RightUpperArm':
          if (rightUpperArmRef.current) rightUpperArmRef.current.quaternion.copy(q);
          break;
        case 'RightLowerArm':
          if (rightLowerArmRef.current) rightLowerArmRef.current.quaternion.copy(q);
          break;
        default:
          break;
      }
    });
  }, [boneRotations]);

  return (
    <group position={[0, -0.6, 0]}>
      {/* ── Pelvis Central ── */}
      <mesh>
        <sphereGeometry args={[0.16, 16, 16]} />
        <meshStandardMaterial color="#444" roughness={0.6} />
      </mesh>

      {/* ── Spine (Tronco de Columna) ── */}
      <group ref={spineRef}>
        {/* Torso */}
        <mesh position={[0, 0.45, 0]}>
          <boxGeometry args={[0.36, 0.9, 0.2]} />
          <meshStandardMaterial color="#e5e5e5" roughness={0.3} metalness={0.1} />
        </mesh>

        {/* Articulación de Cuello */}
        <mesh position={[0, 0.95, 0]}>
          <sphereGeometry args={[0.07, 16, 16]} />
          <meshStandardMaterial color="#8a2be2" roughness={0.4} />
        </mesh>
        
        {/* Cabeza */}
        <mesh position={[0, 1.12, 0]}>
          <boxGeometry args={[0.22, 0.24, 0.22]} />
          <meshStandardMaterial color="#e5e5e5" roughness={0.3} />
        </mesh>

        {/* ── EXTREMIDAD SUPERIOR IZQUIERDA ── */}
        {/* Pivote del Hombro Izquierdo */}
        <group ref={leftUpperArmRef} position={[-0.2, 0.8, 0]}>
          {/* Hombro Izquierdo (Articulación) */}
          <mesh>
            <sphereGeometry args={[0.075, 16, 16]} />
            <meshStandardMaterial color="#8a2be2" roughness={0.4} />
          </mesh>
          {/* Brazo Superior Izquierdo (Cilindro que apunta en -X) */}
          <mesh position={[-0.2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.045, 0.038, 0.4, 16]} />
            <meshStandardMaterial color="#a0a0a0" roughness={0.4} />
          </mesh>

          {/* Pivote del Codo Izquierdo */}
          <group ref={leftLowerArmRef} position={[-0.4, 0, 0]}>
            {/* Codo Izquierdo (Articulación) */}
            <mesh>
              <sphereGeometry args={[0.06, 16, 16]} />
              <meshStandardMaterial color="#8a2be2" roughness={0.4} />
            </mesh>
            {/* Antebrazo Izquierdo (Cilindro que apunta en -X) */}
            <mesh position={[-0.2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.038, 0.03, 0.4, 16]} />
              <meshStandardMaterial color="#6e6e6e" roughness={0.4} />
            </mesh>
            {/* Mano Izquierda (Articulación) */}
            <mesh position={[-0.42, 0, 0]}>
              <sphereGeometry args={[0.042, 16, 16]} />
              <meshStandardMaterial color="#00ffff" roughness={0.4} />
            </mesh>
          </group>
        </group>

        {/* ── EXTREMIDAD SUPERIOR DERECHA ── */}
        {/* Pivote del Hombro Derecho */}
        <group ref={rightUpperArmRef} position={[0.2, 0.8, 0]}>
          {/* Hombro Derecho (Articulación) */}
          <mesh>
            <sphereGeometry args={[0.075, 16, 16]} />
            <meshStandardMaterial color="#8a2be2" roughness={0.4} />
          </mesh>
          {/* Brazo Superior Derecho (Cilindro que apunta en +X) */}
          <mesh position={[0.2, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <cylinderGeometry args={[0.045, 0.038, 0.4, 16]} />
            <meshStandardMaterial color="#a0a0a0" roughness={0.4} />
          </mesh>

          {/* Pivote del Codo Derecho */}
          <group ref={rightLowerArmRef} position={[0.4, 0, 0]}>
            {/* Codo Derecho (Articulación) */}
            <mesh>
              <sphereGeometry args={[0.06, 16, 16]} />
              <meshStandardMaterial color="#8a2be2" roughness={0.4} />
            </mesh>
            {/* Antebrazo Derecho (Cilindro que apunta en +X) */}
            <mesh position={[0.2, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
              <cylinderGeometry args={[0.038, 0.03, 0.4, 16]} />
              <meshStandardMaterial color="#6e6e6e" roughness={0.4} />
            </mesh>
            {/* Mano Derecha (Articulación) */}
            <mesh position={[0.42, 0, 0]}>
              <sphereGeometry args={[0.042, 16, 16]} />
              <meshStandardMaterial color="#00ffff" roughness={0.4} />
            </mesh>
          </group>
        </group>
      </group>
    </group>
  );
};

/**
 * Componente principal del visor 3D que inicializa el canvas de React Three Fiber
 * y agrega controles de cámara, luces y mallas procedimentales ciberpunk.
 */
export const Viewer3D: React.FC<Viewer3DProps> = ({ boneRotations }) => {
  return (
    <div className="panel-terminal" style={{ flex: 1, height: '500px', padding: '0.5rem', position: 'relative' }}>
      <div style={{
        position: 'absolute', top: '15px', left: '15px', zIndex: 10,
        fontSize: '0.7rem', color: '#8e8e8e', pointerEvents: 'none'
      }}>
        [WebGL_RETARGETING_VIEWPORT]
      </div>

      <Canvas
        camera={{ position: [0, 1.2, 2.5], fov: 50 }}
        style={{ background: '#171717', width: '100%', height: '100%' }}
      >
        {/* Iluminación básica de la escena */}
        <ambientLight intensity={0.4} />
        <directionalLight position={[2, 4, 3]} intensity={1.0} castShadow />
        <directionalLight position={[-2, 1, -2]} intensity={0.3} color="#8a2be2" />

        {/* Modelo humanoid procedimental */}
        <HumanoidSkeleton boneRotations={boneRotations} />

        {/* Grilla de base ciberpunk (Helper nativo de Three.js para máxima compatibilidad) */}
        <gridHelper args={[10, 20, '#8a2be2', '#2e2e2e']} position={[0, -0.6, 0]} />

        {/* Controles de cámara de órbita interactivos */}
        <OrbitControls
          enableZoom={true}
          maxPolarAngle={Math.PI / 2 + 0.1}
          target={[0, 0.4, 0]}
        />
      </Canvas>
      
      <div style={{
        position: 'absolute', bottom: '15px', right: '15px', zIndex: 10,
        fontSize: '0.6rem', color: '#00ffff', pointerEvents: 'none'
      }}>
        GRID: 10x10 | ORBIT_ENABLED
      </div>
    </div>
  );
};
