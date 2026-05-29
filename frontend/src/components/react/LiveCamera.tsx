import React, { useEffect, useRef, useState } from 'react';

interface LiveCameraProps {
  /**
   * Método de despacho de WebSocket.
   */
  sendMessage: (msg: any) => void;
  /**
   * Estado actual de conexión del WebSocket.
   */
  isConnected: boolean;
}

/**
 * Componente React que captura video local del usuario (webcam), renderiza un visor ciberpunk
 * y envía frames JPEG a 30 FPS codificados en Base64 al API Gateway.
 * Permite seleccionar el dispositivo de video activo desde un dropdown en tiempo real.
 */
export const LiveCamera: React.FC<LiveCameraProps> = ({ sendMessage, isConnected }) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [streamActive, setStreamActive] = useState(false);
  const [fps, setFps] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const frameIdRef = useRef(0);

  // Consultar dispositivos de video disponibles una vez otorgados los permisos
  useEffect(() => {
    const queryDevices = async () => {
      if (typeof window === 'undefined' || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        return;
      }
      try {
        const allDevices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = allDevices.filter(device => device.kind === 'videoinput');
        setDevices(videoDevices);
      } catch (err) {
        console.error("Error al enumerar dispositivos multimedia:", err);
      }
    };

    if (streamActive) {
      queryDevices();
    }
  }, [streamActive]);

  // Inicializar captura de video WebRTC al montar o cambiar de cámara seleccionada
  useEffect(() => {
    let active = true;
    let stream: MediaStream | null = null;

    const startCamera = async () => {
      // Protección de contexto seguro
      if (typeof window === 'undefined' || !navigator.mediaDevices) {
        setErrorMessage("Dispositivo de video no accesible (contexto no seguro o navegador incompatible).");
        return;
      }

      const constraints: MediaStreamConstraints = {
        video: selectedDeviceId 
          ? { deviceId: { exact: selectedDeviceId } } 
          : { 
              width: { ideal: 640 }, 
              height: { ideal: 480 }, 
              frameRate: { ideal: 30 } 
            },
        audio: false
      };

      try {
        // Intentar iniciar con restricciones
        stream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (err: any) {
        console.warn("Falla al iniciar cámara con restricciones. Intentando fallback sin restricciones...", err);
        try {
          // Fallback sin restricciones (ideal para cámaras virtuales o móviles conectadas por enlace de Windows)
          stream = await navigator.mediaDevices.getUserMedia({
            video: selectedDeviceId ? { deviceId: { exact: selectedDeviceId } } : true,
            audio: false
          });
        } catch (fallbackErr: any) {
          console.error("Falla crítica al inicializar dispositivo de video:", fallbackErr);
          if (active) {
            setErrorMessage(`Acceso a cámara rechazado: ${fallbackErr.message || fallbackErr}`);
          }
          return;
        }
      }

      if (videoRef.current && active && stream) {
        videoRef.current.srcObject = stream;
        setStreamActive(true);
        setErrorMessage(null); // Limpiar errores anteriores
      }
    };

    startCamera();

    return () => {
      active = false;
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, [selectedDeviceId]);

  // Bucle de captura y envío de frames
  useEffect(() => {
    if (!streamActive || !isConnected) return;

    let intervalId: number;
    let lastTime = performance.now();
    let frameCount = 0;

    const captureFrame = () => {
      if (!videoRef.current || !canvasRef.current) return;
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Dibujar cuadro actual de video en el canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Comprimir a JPEG Base64 de peso mínimo (calidad 0.6)
      const base64Data = canvas.toDataURL('image/jpeg', 0.6);

      // Incrementar secuenciador
      frameIdRef.current += 1;

      // Transmitir al WebSocket del Gateway
      sendMessage({
        frame_id: frameIdRef.current,
        frame_data: base64Data
      });

      // Medición de FPS en el cliente
      frameCount++;
      const now = performance.now();
      if (now - lastTime >= 1000) {
        setFps(frameCount);
        frameCount = 0;
        lastTime = now;
      }
    };

    // Temporizador preciso a 33ms (30 FPS)
    intervalId = setInterval(captureFrame, 33) as unknown as number;

    return () => {
      clearInterval(intervalId);
    };
  }, [streamActive, isConnected, sendMessage]);

  return (
    <div className="panel-terminal" style={{ padding: '1rem', width: '320px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.75rem' }}>
        <span style={{ color: isConnected ? '#00ffff' : '#ff3333', fontWeight: 'bold' }}>
          ● {isConnected ? 'LINKED_TO_GATEWAY' : 'DISCONNECTED'}
        </span>
        <span style={{ color: '#8e8e8e' }}>CAPTURE_FPS: {fps}</span>
      </div>

      {/* Selector de cámara si hay múltiples dispositivos */}
      {devices.length > 1 && (
        <div style={{ marginBottom: '0.75rem' }}>
          <label style={{ 
            fontSize: '0.65rem', 
            color: 'var(--text-muted)', 
            display: 'block', 
            marginBottom: '0.25rem',
            letterSpacing: '0.05em'
          }}>
            &gt; ACTIVE_INPUT_DEVICE:
          </label>
          <select
            value={selectedDeviceId}
            onChange={(e) => setSelectedDeviceId(e.target.value)}
            style={{
              width: '100%',
              backgroundColor: '#171717',
              color: 'var(--text-main)',
              border: '1px solid #333',
              padding: '0.35rem',
              fontSize: '0.68rem',
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            {devices.map((device, idx) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label || `Camera ${idx + 1}`}
              </option>
            ))}
          </select>
        </div>
      )}

      <div style={{ position: 'relative', width: '100%', height: '210px', backgroundColor: '#000', border: '1px solid #333' }}>
        {errorMessage ? (
          <div style={{ 
            padding: '1rem', 
            fontSize: '0.7rem', 
            color: '#ff4444', 
            fontFamily: 'monospace',
            textAlign: 'center',
            display: 'flex',
            alignItems: 'center',
            height: '100%' 
          }}>
            [CAM_ERROR]: {errorMessage}
          </div>
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ 
              width: '100%', 
              height: '100%', 
              objectFit: 'cover', 
              filter: 'grayscale(100%) contrast(140%) brightness(75%)' 
            }}
          />
        )}
        <canvas
          ref={canvasRef}
          width={320}
          height={240}
          style={{ display: 'none' }}
        />

        {/* Rejilla holográfica estilo HUD */}
        <div style={{
          position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
          backgroundImage: 'linear-gradient(rgba(0, 255, 255, 0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 255, 255, 0.04) 1px, transparent 1px)',
          backgroundSize: '16px 16px',
          pointerEvents: 'none'
        }} />

        {/* Overlay de grabación parpadeante */}
        <div style={{
          position: 'absolute', 
          top: '10px', 
          left: '10px', 
          fontSize: '0.65rem',
          color: '#00ffff', 
          fontWeight: 'bold',
          letterSpacing: '0.1em'
        }}>
          ● REC_LIVE [DEV_MODE]
        </div>

        <div style={{
          position: 'absolute', 
          bottom: '10px', 
          right: '10px', 
          fontSize: '0.6rem',
          color: '#8e8e8e', 
          fontFamily: 'monospace'
        }}>
          CAM_RES: 640x480
        </div>
      </div>
    </div>
  );
};
