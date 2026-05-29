import React, { useState } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import type { BoneRotation } from '../../hooks/useWebSocket';
import { LiveCamera } from './LiveCamera';
import { Viewer3D } from './Viewer3D';

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

/**
 * Componente principal del MVP de BioRender.
 * Orquesta la captura de tramas y el envío por WS, y actualiza la animación del avatar.
 */
const BioRenderMain: React.FC = () => {
  const [boneRotations, setBoneRotations] = useState<BoneRotation[]>([]);
  
  // Dirección de conexión WebSocket al API Gateway local
  const wsUrl = 'ws://localhost:8080/ws/live-pose';
  
  const { isConnected, sendMessage } = useWebSocket(wsUrl, (data) => {
    if (data.bone_rotations) {
      setBoneRotations(data.bone_rotations);
    }
  });

  return (
    <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', width: '100%' }}>
      {/* ── Columna de Controles e Información del Sistema ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <LiveCamera sendMessage={sendMessage} isConnected={isConnected} />
        
        {/* Panel de estado retro ciberpunk */}
        <div className="panel-terminal" style={{ width: '320px', fontSize: '0.75rem', color: '#8e8e8e' }}>
          <h3 style={{ 
            fontSize: '0.8rem', 
            color: '#f5f5f5', 
            marginBottom: '0.5rem', 
            fontFamily: 'var(--font-mono)' 
          }}>
            &gt; SYSTEM_METRICS
          </h3>
          <p style={{ margin: '0.25rem 0' }}>• LATENCY_TARGET: &lt; 50ms</p>
          <p style={{ margin: '0.25rem 0' }}>• INFERENCE: MediaPipe Pose CPU (RT)</p>
          <p style={{ margin: '0.25rem 0' }}>• RUST_GATEWAY: Active (Axum/Tokio)</p>
          <p style={{ margin: '0.25rem 0', color: isConnected ? '#00ffff' : '#ff3333', fontWeight: 'bold' }}>
            • GATEWAY_LINK: {isConnected ? 'ONLINE_READY' : 'OFFLINE_ATTEMPTING'}
          </p>
        </div>
      </div>

      {/* ── Viewport 3D en Tiempo Real ── */}
      <Viewer3D boneRotations={boneRotations} />
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
