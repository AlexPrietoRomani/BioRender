import React, { useRef, useEffect, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import type { BoneRotation } from '../../hooks/useWebSocket';

interface Viewer3DProps {
  /**
   * Colección de rotaciones de hueso calculadas en el Gateway.
   */
  boneRotations?: BoneRotation[];
  /**
   * URL del modelo GLB a cargar dinámicamente.
   */
  modelUrl?: string | null;
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
      {/* Pelvis Central */}
      <mesh>
        <sphereGeometry args={[0.16, 16, 16]} />
        <meshStandardMaterial color="#444" roughness={0.6} />
      </mesh>

      {/* Spine (Tronco de Columna) */}
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

        {/* EXTREMIDAD SUPERIOR IZQUIERDA */}
        {/* Pivote del Hombro Izquierdo */}
        <group ref={leftUpperArmRef} position={[-0.2, 0.8, 0]}>
          <mesh>
            <sphereGeometry args={[0.075, 16, 16]} />
            <meshStandardMaterial color="#8a2be2" roughness={0.4} />
          </mesh>
          <mesh position={[-0.2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.045, 0.038, 0.4, 16]} />
            <meshStandardMaterial color="#a0a0a0" roughness={0.4} />
          </mesh>

          {/* Pivote del Codo Izquierdo */}
          <group ref={leftLowerArmRef} position={[-0.4, 0, 0]}>
            <mesh>
              <sphereGeometry args={[0.06, 16, 16]} />
              <meshStandardMaterial color="#8a2be2" roughness={0.4} />
            </mesh>
            <mesh position={[-0.2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.038, 0.03, 0.4, 16]} />
              <meshStandardMaterial color="#6e6e6e" roughness={0.4} />
            </mesh>
            <mesh position={[-0.42, 0, 0]}>
              <sphereGeometry args={[0.042, 16, 16]} />
              <meshStandardMaterial color="#00ffff" roughness={0.4} />
            </mesh>
          </group>
        </group>

        {/* EXTREMIDAD SUPERIOR DERECHA */}
        {/* Pivote del Hombro Derecho */}
        <group ref={rightUpperArmRef} position={[0.2, 0.8, 0]}>
          <mesh>
            <sphereGeometry args={[0.075, 16, 16]} />
            <meshStandardMaterial color="#8a2be2" roughness={0.4} />
          </mesh>
          <mesh position={[0.2, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <cylinderGeometry args={[0.045, 0.038, 0.4, 16]} />
            <meshStandardMaterial color="#a0a0a0" roughness={0.4} />
          </mesh>

          {/* Pivote del Codo Derecho */}
          <group ref={rightLowerArmRef} position={[0.4, 0, 0]}>
            <mesh>
              <sphereGeometry args={[0.06, 16, 16]} />
              <meshStandardMaterial color="#8a2be2" roughness={0.4} />
            </mesh>
            <mesh position={[0.2, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
              <cylinderGeometry args={[0.038, 0.03, 0.4, 16]} />
              <meshStandardMaterial color="#6e6e6e" roughness={0.4} />
            </mesh>
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
 * Componente que carga dinámicamente un modelo GLB y lo anima en tiempo real.
 */
const DynamicGlbModel: React.FC<{ url: string; boneRotations?: BoneRotation[] }> = ({ url, boneRotations = [] }) => {
  const { scene } = useGLTF(url);
  
  // Clonar la escena para asegurar renderizados seguros en múltiples visores
  const clonedScene = React.useMemo(() => scene.clone(), [scene]);
  
  useEffect(() => {
    if (!boneRotations || boneRotations.length === 0) return;
    
    boneRotations.forEach((rot) => {
      const targetName = rot.bone_name; // 'LeftUpperArm', 'LeftLowerArm', etc.
      
      // Intentar mapear los nombres estándar a las nomenclaturas usuales de Mixamo en GLTF
      const boneNamesToTry = [
        targetName,
        `mixamorig:${targetName}`,
        `mixamorig${targetName}`,
        targetName.toLowerCase(),
        // Traducir a nomenclatura Mixamo canónica
        targetName === 'Spine' ? 'mixamorigSpine' : '',
        targetName === 'LeftUpperArm' ? 'mixamorigLeftArm' : '',
        targetName === 'LeftLowerArm' ? 'mixamorigLeftForeArm' : '',
        targetName === 'RightUpperArm' ? 'mixamorigRightArm' : '',
        targetName === 'RightLowerArm' ? 'mixamorigRightForeArm' : '',
      ].filter(Boolean);
      
      let boneObject: THREE.Object3D | null = null;
      for (const name of boneNamesToTry) {
        boneObject = clonedScene.getObjectByName(name!);
        if (boneObject) break;
      }
      
      if (boneObject) {
        const q = new THREE.Quaternion(
          rot.quaternion[0],
          rot.quaternion[1],
          rot.quaternion[2],
          rot.quaternion[3]
        );
        boneObject.quaternion.copy(q);
      }
    });
  }, [boneRotations, clonedScene]);
  
  return <primitive object={clonedScene} position={[0, -0.6, 0]} scale={[0.8, 0.8, 0.8]} />;
};

/**
 * Indicador de carga animado en 3D para el visor WebGL.
 */
const LoadingSpinner: React.FC = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.getElapsedTime() * 1.5;
      meshRef.current.rotation.x = state.clock.getElapsedTime() * 0.7;
    }
  });

  return (
    <mesh ref={meshRef} position={[0, 0.4, 0]}>
      <boxGeometry args={[0.4, 0.4, 0.4]} />
      <meshStandardMaterial color="#00f07f" wireframe roughness={0.1} />
    </mesh>
  );
};

/**
 * Componente principal del visor 3D que inicializa el canvas de React Three Fiber
 * y agrega controles de cámara, luces y mallas procedimentales ciberpunk.
 */
export const Viewer3D: React.FC<Viewer3DProps> = ({ boneRotations = [], modelUrl = null }) => {
  return (
    <div className="panel-terminal" style={{ flex: 1, height: '100%', minHeight: '450px', padding: '0.5rem', position: 'relative', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', top: '15px', left: '15px', zIndex: 10,
        fontSize: '0.7rem', color: '#00f07f', pointerEvents: 'none',
        fontFamily: 'var(--font-mono)', letterSpacing: '0.05em'
      }}>
        {modelUrl ? '[GLB_RENDER_VIEWPORT]' : '[PROCEDURAL_SKELETON_VIEWPORT]'}
      </div>

      <Canvas
        camera={{ position: [0, 1.0, 2.2], fov: 45 }}
        style={{ background: '#0a0a0c', width: '100%', height: '100%' }}
      >
        {/* Iluminación base */}
        <ambientLight intensity={0.5} />
        <directionalLight position={[3, 5, 4]} intensity={1.2} castShadow />
        <directionalLight position={[-3, 1, -2]} intensity={0.4} color="#8a2be2" />
        <pointLight position={[0, 2, 0]} intensity={0.6} color="#00f07f" />

        {/* Renderizado condicional del modelo GLB o el esqueleto procedimental */}
        {modelUrl ? (
          <Suspense fallback={<LoadingSpinner />}>
            <DynamicGlbModel url={modelUrl} boneRotations={boneRotations} />
          </Suspense>
        ) : (
          <HumanoidSkeleton boneRotations={boneRotations} />
        )}

        {/* Grilla cyberpunk */}
        <gridHelper args={[12, 24, '#00f07f', '#1b1b22']} position={[0, -0.6, 0]} />

        {/* Controles de cámara */}
        <OrbitControls
          enableZoom={true}
          maxPolarAngle={Math.PI / 2 + 0.05}
          target={[0, 0.4, 0]}
        />
      </Canvas>
      
      <div style={{
        position: 'absolute', bottom: '15px', right: '15px', zIndex: 10,
        fontSize: '0.65rem', color: '#8e8e8e', pointerEvents: 'none',
        fontFamily: 'var(--font-mono)'
      }}>
        {modelUrl ? 'SOURCE: OBJECT_STORAGE (S3)' : 'SOURCE: WEBSOCKET_RT'}
      </div>
    </div>
  );
};
