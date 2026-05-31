import React, { useRef } from 'react';

interface VideoPlayerProps {
  /**
   * URL de la firma temporal para reproducir el video MP4 renderizado.
   */
  videoUrl: string | null;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl }) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  return (
    <div className="panel-terminal" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem', minHeight: '450px', padding: '0.5rem', position: 'relative', overflow: 'hidden' }}>
      <div style={{
        fontSize: '0.7rem', color: '#00f07f',
        fontFamily: 'var(--font-mono)', letterSpacing: '0.05em',
        marginBottom: '0.25rem'
      }}>
        [MP4_BLENDER_RENDER_VIEWPORT]
      </div>

      {videoUrl ? (
        <div style={{ position: 'relative', width: '100%', height: 'calc(100% - 25px)', minHeight: '380px', background: '#000000', border: '1px solid #1b1b22', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <video
            ref={videoRef}
            src={videoUrl}
            controls
            autoPlay
            loop
            playsInline
            style={{
              width: '100%',
              height: '100%',
              maxHeight: '420px',
              objectFit: 'contain',
              outline: 'none'
            }}
          />
        </div>
      ) : (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0a0a0c',
          border: '1px solid #1b1b22',
          minHeight: '380px',
          color: '#8e8e8e',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          textAlign: 'center',
          padding: '2rem'
        }}>
          <div>&gt; ESPERANDO_RENDER_MULTIMEDIA...</div>
          <div style={{ fontSize: '0.65rem', color: '#4a4a5a', marginTop: '0.5rem' }}>
            Completa la extracción y renderizado del Pipeline B para proyectar el video.
          </div>
        </div>
      )}

      <div style={{
        position: 'absolute', bottom: '15px', right: '15px', zIndex: 10,
        fontSize: '0.65rem', color: '#8e8e8e', pointerEvents: 'none',
        fontFamily: 'var(--font-mono)'
      }}>
        CODEC: H.264 MP4 | EEVEE_GPU
      </div>
    </div>
  );
};
