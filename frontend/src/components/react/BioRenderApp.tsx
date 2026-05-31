import React, { useState } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import type { BoneRotation } from '../../hooks/useWebSocket';
import { LiveCamera } from './LiveCamera';
import { Viewer3D } from './Viewer3D';
import { ImageUploader } from './ImageUploader';
import { VideoUploader } from './VideoUploader';
import { VideoPlayer } from './VideoPlayer';

/**
 * Componente Boundary para capturar fallas de renderizado en React (ej: WebGL crash).
 */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }

  componentDidCatch(error: any, errorInfo: any) {
    console.error("Error capturado por ErrorBoundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="panel-terminal" style={{ padding: '2rem', border: '2px solid #ff3333', color: '#ff3333', width: '100%' }}>
          <h2 style={{ fontSize: '1rem', marginBottom: '1rem' }}>
            [RUNTIME_CRASH_DETECTED]
          </h2>
          <p style={{ marginBottom: '1rem', fontSize: '0.8rem', color: '#f5f5f5' }}>
            Se produjo un error crítico al inicializar la escena 3D WebGL o al capturar la cámara:
          </p>
          <pre style={{ 
            background: '#000', 
            padding: '1rem', 
            overflowX: 'auto', 
            fontSize: '0.75rem',
            color: '#ff3333',
            border: '1px solid #333'
          }}>
            {this.state.error?.toString()}
          </pre>
          <button 
            className="btn-retro" 
            style={{ marginTop: '1.5rem', display: 'inline-block' }}
            onClick={() => window.location.reload()}
          >
            REINICIAR SISTEMA
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

type TabType = 'realtime' | 'generation' | 'retargeting';

/**
 * Componente principal del monorepo BioRender.
 * Unifica las 3 fases en una sola interfaz interactiva tipo cabina de control.
 */
const BioRenderMain: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('realtime');
  const [boneRotations, setBoneRotations] = useState<BoneRotation[]>([]);
  
  // Estados para persistir las subidas y los resultados de jobs entre pestañas
  const [avatarGlbUrl, setAvatarGlbUrl] = useState<string | null>(null);
  const [avatarJobId, setAvatarJobId] = useState<string | null>(null);
  const [renderedVideoUrl, setRenderedVideoUrl] = useState<string | null>(null);
  const [videoJobId, setVideoJobId] = useState<string | null>(null);

  // Obtener URL de WebSocket de las variables de entorno
  const wsUrl = import.meta.env.PUBLIC_GATEWAY_WS_URL || 'ws://localhost:8080/ws/live-pose';
  
  const { isConnected, sendMessage } = useWebSocket(wsUrl, (data) => {
    if (data.bone_rotations) {
      setBoneRotations(data.bone_rotations);
    }
  });

  // Manejador para finalizar la generación del Avatar (Pipeline A)
  const handleGenerationComplete = (glbUrl: string, jobId: string) => {
    setAvatarGlbUrl(glbUrl);
    setAvatarJobId(jobId);
  };

  // Manejador para finalizar el retargeting y renderizado de video (Pipeline B)
  const handleRetargetingComplete = (videoUrl: string, jobId: string) => {
    setRenderedVideoUrl(videoUrl);
    setVideoJobId(jobId);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%' }}>
      
      {/* ── Navegación Cyberpunk por Pestañas ── */}
      <div style={{ display: 'flex', borderBottom: '2px solid #1b1b22', paddingBottom: '0.25rem', gap: '0.5rem' }}>
        <button
          className={activeTab === 'realtime' ? 'btn-retro active' : 'btn-retro'}
          onClick={() => setActiveTab('realtime')}
          style={{ padding: '0.5rem 1rem', fontSize: '0.75rem', borderBottom: activeTab === 'realtime' ? '2px solid #00f07f' : 'none' }}
        >
          [ STREAM EN VIVO ]
        </button>
        <button
          className={activeTab === 'generation' ? 'btn-retro active' : 'btn-retro'}
          onClick={() => setActiveTab('generation')}
          style={{ padding: '0.5rem 1rem', fontSize: '0.75rem', borderBottom: activeTab === 'generation' ? '2px solid #00f07f' : 'none' }}
        >
          [ CREAR AVATAR 3D ]
        </button>
        <button
          className={activeTab === 'retargeting' ? 'btn-retro active' : 'btn-retro'}
          onClick={() => setActiveTab('retargeting')}
          style={{ padding: '0.5rem 1rem', fontSize: '0.75rem', borderBottom: activeTab === 'retargeting' ? '2px solid #00f07f' : 'none' }}
        >
          [ RETARGETING & RENDER ]
        </button>
      </div>

      {/* ── Contenido de las Pestañas ── */}
      
      {/* 1. MODO: STREAM EN VIVO (Realtime WebSocket) */}
      {activeTab === 'realtime' && (
        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', width: '100%' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <LiveCamera sendMessage={sendMessage} isConnected={isConnected} />
            
            {/* Panel de estado */}
            <div className="panel-terminal" style={{ width: '320px', fontSize: '0.75rem', color: '#8e8e8e' }}>
              <h3 style={{ fontSize: '0.8rem', color: '#f5f5f5', marginBottom: '0.5rem', fontFamily: 'var(--font-mono)' }}>
                &gt; SYSTEM_METRICS (RT)
              </h3>
              <p style={{ margin: '0.25rem 0' }}>• TARGET_LATENCY: &lt; 50ms</p>
              <p style={{ margin: '0.25rem 0' }}>• MODEL: MediaPipe Pose CPU Fallback</p>
              <p style={{ margin: '0.25rem 0' }}>• proxy_cam_socket: Active (Axum/Tokio)</p>
              <p style={{ margin: '0.25rem 0', color: isConnected ? '#00f07f' : '#ff3333', fontWeight: 'bold' }}>
                • GATEWAY_LINK: {isConnected ? 'ONLINE_READY' : 'OFFLINE_RETRY'}
              </p>
            </div>
          </div>
          
          <div style={{ flex: 1, display: 'flex' }}>
            <Viewer3D boneRotations={boneRotations} />
          </div>
        </div>
      )}

      {/* 2. MODO: CREAR AVATAR 3D (Pipeline A) */}
      {activeTab === 'generation' && (
        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', width: '100%' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%', maxWidth: '480px' }}>
            <ImageUploader onGenerationComplete={handleGenerationComplete} />
            
            {avatarJobId && (
              <div className="panel-terminal" style={{ fontSize: '0.75rem', color: '#8e8e8e' }}>
                <h3 style={{ fontSize: '0.8rem', color: '#f5f5f5', marginBottom: '0.5rem', fontFamily: 'var(--font-mono)' }}>
                  &gt; AVATAR_METADATA
                </h3>
                <p style={{ margin: '0.25rem 0', wordBreak: 'break-all' }}>• HASH_JOB_ID: {avatarJobId}</p>
                <p style={{ margin: '0.25rem 0', color: '#00f07f', fontWeight: 'bold' }}>• COMPILATION: SUCCESSFUL_GLB</p>
              </div>
            )}
          </div>
          
          <div style={{ flex: 1, display: 'flex' }}>
            <Viewer3D modelUrl={avatarGlbUrl} />
          </div>
        </div>
      )}

      {/* 3. MODO: RETARGETING Y RENDER (Pipeline B - Visor Dual) */}
      {activeTab === 'retargeting' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', width: '100%' }}>
          <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', width: '100%' }}>
            <div style={{ width: '100%', maxWidth: '480px' }}>
              <VideoUploader
                defaultAvatarJobId={avatarJobId}
                onRetargetingComplete={handleRetargetingComplete}
              />
            </div>
            
            {videoJobId && (
              <div className="panel-terminal" style={{ flex: 1, fontSize: '0.75rem', color: '#8e8e8e', minWidth: '300px' }}>
                <h3 style={{ fontSize: '0.8rem', color: '#f5f5f5', marginBottom: '0.5rem', fontFamily: 'var(--font-mono)' }}>
                  &gt; MOTION_METADATA
                </h3>
                <p style={{ margin: '0.25rem 0', wordBreak: 'break-all' }}>• MOTION_JOB_ID: {videoJobId}</p>
                <p style={{ margin: '0.25rem 0' }}>• RENDER_ENGINE: Blender Headless Eevee (GPU)</p>
                <p style={{ margin: '0.25rem 0', color: '#00f07f', fontWeight: 'bold' }}>• RETARGETING_STATUS: SUCCESS_RENDER_MP4</p>
              </div>
            )}
          </div>

          {/* Visor Dual en Paralelo */}
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', width: '100%' }}>
            {/* Izquierda: Visor 3D del Avatar compilado */}
            <div style={{ flex: 1, minWidth: '400px', display: 'flex' }}>
              <Viewer3D modelUrl={avatarGlbUrl} />
            </div>

            {/* Derecha: VideoPlayer del Render de Blender */}
            <div style={{ flex: 1, minWidth: '400px', display: 'flex' }}>
              <VideoPlayer videoUrl={renderedVideoUrl} />
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export const BioRenderApp: React.FC = () => {
  return (
    <ErrorBoundary>
      <BioRenderMain />
    </ErrorBoundary>
  );
};
