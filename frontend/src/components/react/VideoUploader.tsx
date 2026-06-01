import React, { useState, useRef, useEffect } from 'react';
import { useSessionStore } from './sessionStore';

interface VideoUploaderProps {
  /**
   * ID predeterminado del avatar generado en el Pipeline A en la sesión actual.
   */
  defaultAvatarJobId?: string | null;
  /**
   * Callback ejecutado al finalizar exitosamente el retargeting y renderizado de video.
   * Proporciona la URL del video MP4 final.
   */
  onRetargetingComplete: (videoUrl: string, jobId: string) => void;
}

interface JobState {
  status: string;
  progress: number;
  error?: string | null;
  jobId: string | null;
}

export const VideoUploader: React.FC<VideoUploaderProps> = ({ defaultAvatarJobId = null, onRetargetingComplete }) => {
  const { avatarsList, activeAvatarUrl } = useSessionStore();
  const [file, setFile] = useState<File | null>(null);
  const [avatarJobId, setAvatarJobId] = useState<string>('');
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [jobState, setJobState] = useState<JobState>({
    status: 'idle',
    progress: 0,
    error: null,
    jobId: null
  });
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Guardar el tiempo de inicio para el cronometraje total
  const totalStartTimeRef = useRef<number>(0);

  const gatewayHttpUrl = import.meta.env.PUBLIC_GATEWAY_HTTP_URL || 'http://localhost:8080';

  // Si cambia el listado de avatares y no tenemos uno seleccionado, autoseleccionar el primero
  useEffect(() => {
    if (avatarsList.length > 0) {
      // Si hay un defaultAvatarJobId preferimos ese, sino el último en la lista
      const match = avatarsList.find(a => a.id === defaultAvatarJobId);
      if (match) {
        setAvatarJobId(match.id);
      } else if (!avatarJobId || !avatarsList.some(a => a.id === avatarJobId)) {
        setAvatarJobId(avatarsList[avatarsList.length - 1].id);
      }
    } else {
      setAvatarJobId('');
    }
  }, [avatarsList, defaultAvatarJobId]);

  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setTerminalLogs((prev) => [...prev, `[${timestamp}] ${msg}`]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    const isVideo = selectedFile.type.startsWith('video/') || selectedFile.name.endsWith('.mp4') || selectedFile.name.endsWith('.webm');
    if (isVideo) {
      setFile(selectedFile);
      setJobState({ status: 'idle', progress: 0, error: null, jobId: null });
      setTerminalLogs([]);
      addLog(`Video seleccionado: ${selectedFile.name} (${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)`);
    } else {
      addLog("ERROR: El archivo seleccionado debe ser un video (MP4/WebM).");
    }
  };

  const triggerFileSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const startRetargeting = async () => {
    if (!file) return;
    if (!avatarJobId) {
      addLog("ERROR: Debe seleccionar un avatar de destino para realizar el retargeting.");
      return;
    }

    setUploading(true);
    setTerminalLogs([]);
    addLog("Iniciando Pipeline B: Extracción de Pose y Render Headless...");
    const selectedAvatar = avatarsList.find(a => a.id === avatarJobId);
    addLog(`Avatar Destino: ${selectedAvatar ? selectedAvatar.name : avatarJobId} (${avatarJobId})`);
    addLog("Preparando carga multipart...");

    const formData = new FormData();
    formData.append('video', file);
    formData.append('avatar_job_id', avatarJobId.trim());

    const uploadStart = performance.now();
    totalStartTimeRef.current = performance.now();

    try {
      addLog(`Subiendo video a MinIO mediante Gateway en ${gatewayHttpUrl}/api/process-video...`);
      const res = await fetch(`${gatewayHttpUrl}/api/process-video`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `HTTP error! status: ${res.status}`);
      }

      const data = await res.json();
      const jobId = data.job_id;
      const uploadDuration = performance.now() - uploadStart;

      addLog(`[PERF_LOG] Subida de video completada (Duración: ${uploadDuration.toFixed(0)}ms)`);
      addLog(`¡Video almacenado con éxito! Job ID asignado: ${jobId}`);
      addLog("Tarea de extracción encolada en Celery (cola: 'motion').");
      
      setJobState({
        status: 'queued',
        progress: 0,
        error: null,
        jobId
      });

      // Iniciar polling
      startPolling(jobId);

    } catch (err: any) {
      addLog(`ERROR CRÍTICO DE PROCESAMIENTO: ${err.message}`);
      setJobState({
        status: 'error',
        progress: 0,
        error: err.message,
        jobId: null
      });
      setUploading(false);
    }
  };

  const startPolling = (jobId: string) => {
    addLog("Inicializando polling de seguimiento de renderizado (intervalo: 3000ms)...");

    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(`${gatewayHttpUrl}/api/jobs/${jobId}`);
        if (!res.ok) {
          throw new Error(`Error en polling: ${res.status}`);
        }

        const data = await res.json();
        const status = data.status;
        const progress = data.progress || 0;

        addLog(`Consulta de progreso: [${status.toUpperCase()}] | Progreso: ${progress}%`);

        if (status === 'done' || status === 'success') {
          clearInterval(intervalId);
          const totalDuration = performance.now() - totalStartTimeRef.current;
          addLog("¡PROCESAMIENTO DE RETARGETING Y RENDERIZADO COMPLETADO!");
          addLog(`[PERF_LOG] Tiempo Total del Render: ${totalDuration.toFixed(0)}ms`);
          addLog("Generando URL pre-firmada del video renderizado en Blender Eevee...");

          setJobState({
            status: 'done',
            progress: 100,
            error: null,
            jobId
          });
          setUploading(false);

          // Retornar la URL pre-firmada del video para reproducirlo
          onRetargetingComplete(data.result_url, jobId);

        } else if (status === 'error' || status === 'failed') {
          clearInterval(intervalId);
          const errMsg = data.error_message || "Fallo en la estimación cinemática WHAM o en Blender Headless.";
          addLog(`[PIPELINE_ERROR] ${errMsg}`);
          setJobState({
            status: 'error',
            progress: progress,
            error: errMsg,
            jobId
          });
          setUploading(false);
        } else {
          setJobState({
            status,
            progress,
            error: null,
            jobId
          });
        }

      } catch (err: any) {
        addLog(`[WARNING_POLLING] ${err.message}. Reintentando...`);
      }
    }, 3000);
  };

  const hasAvatars = avatarsList.length > 0;

  return (
    <div className="panel-terminal" style={{ width: '100%', maxWidth: '480px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ fontSize: '0.85rem', color: '#00f07f', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>
        &gt; PIPELINE_B: VIDEO_RETARGETING
      </h3>

      {/* Selector del Avatar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <label style={{ fontSize: '0.65rem', color: '#8e8e8e', fontFamily: 'var(--font-mono)' }}>SELECCIONAR AVATAR DESTINO:</label>
        {hasAvatars ? (
          <select
            value={avatarJobId}
            onChange={(e) => setAvatarJobId(e.target.value)}
            disabled={uploading}
            style={{
              background: '#0a0a0c',
              border: '2px solid #1b1b22',
              color: '#f5f5f5',
              padding: '0.5rem',
              fontSize: '0.8rem',
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              width: '100%',
              boxSizing: 'border-box',
              cursor: 'pointer'
            }}
          >
            {avatarsList.map((avatar) => (
              <option key={avatar.id} value={avatar.id}>
                {avatar.name} ({avatar.id.slice(0, 8)}...)
              </option>
            ))}
          </select>
        ) : (
          <div style={{
            padding: '0.75rem',
            background: '#ff333315',
            border: '2px solid #ff3333',
            color: '#ff3333',
            fontSize: '0.7rem',
            fontFamily: 'var(--font-mono)',
            lineHeight: '1.4'
          }}>
            [ALERTA SISTEMA] No hay avatares creados en esta sesión. Primero debes ir a la pestaña "Compilar Avatar" y crear al menos un personaje 3D con rostro para poder animarlo aquí.
          </div>
        )}
      </div>

      {/* Área de arrastrar y soltar */}
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={triggerFileSelect}
        style={{
          border: dragActive ? '2px dashed #00f07f' : '2px solid #1b1b22',
          background: dragActive ? '#00f07f08' : '#0a0a0c',
          padding: '2rem 1rem',
          textAlign: 'center',
          cursor: (!hasAvatars || uploading) ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s ease',
          pointerEvents: (!hasAvatars || uploading) ? 'none' : 'auto',
          opacity: hasAvatars ? 1 : 0.4
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          onChange={handleChange}
          style={{ display: 'none' }}
          disabled={!hasAvatars}
        />
        
        {file ? (
          <div>
            <div style={{ color: '#f5f5f5', fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.5rem', wordBreak: 'break-all' }}>
              {file.name}
            </div>
            <div style={{ color: '#8e8e8e', fontSize: '0.65rem' }}>
              Haz clic para reemplazar el video de movimiento
            </div>
          </div>
        ) : (
          <div>
            <div style={{ color: '#8e8e8e', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
              Arrastra un video de actor aquí (.mp4 / .webm)
            </div>
            <div style={{ color: '#00f07f', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 'bold' }}>
              o busca en tu dispositivo
            </div>
          </div>
        )}
      </div>

      {file && !uploading && jobState.status === 'idle' && hasAvatars && (
        <button
          className="btn-retro"
          onClick={startRetargeting}
          style={{ width: '100%', textTransform: 'uppercase' }}
        >
          EJECUTAR RETARGETING Y RENDER
        </button>
      )}

      {/* Monitor de Progreso */}
      {jobState.status !== 'idle' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', fontFamily: 'var(--font-mono)' }}>
            <span style={{ color: '#8e8e8e' }}>JOB_STATUS: <span style={{ color: jobState.status === 'error' ? '#ff3333' : '#00f07f', fontWeight: 'bold' }}>{jobState.status.toUpperCase()}</span></span>
            <span style={{ color: '#00f07f' }}>{jobState.progress}%</span>
          </div>
          
          <div style={{ width: '100%', height: '8px', background: '#1b1b22', border: '1px solid #2e2e2e', overflow: 'hidden' }}>
            <div
              style={{
                width: `${jobState.progress}%`,
                height: '100%',
                background: jobState.status === 'error' ? '#ff3333' : '#00f07f',
                transition: 'width 0.4s ease-out'
              }}
            />
          </div>
        </div>
      )}

      {/* Logs del Terminal */}
      {terminalLogs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ fontSize: '0.65rem', color: '#8e8e8e', fontFamily: 'var(--font-mono)' }}>&gt; TERMINAL_LOGS:</div>
          <div
            style={{
              background: '#000000',
              border: '1px solid #1b1b22',
              padding: '0.5rem',
              height: '110px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.2rem',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: '#d5d5d5'
            }}
          >
            {terminalLogs.map((log, idx) => (
              <div key={idx} style={{ 
                color: log.includes('ERROR') ? '#ff3333' : log.includes('SUCCESS') || log.includes('FINALIZADO') || log.includes('[PERF_LOG]') ? '#00f07f' : '#d5d5d5',
                wordBreak: 'break-all'
              }}>
                {log}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
