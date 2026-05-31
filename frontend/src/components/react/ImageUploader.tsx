import React, { useState, useRef } from 'react';

interface ImageUploaderProps {
  /**
   * Callback ejecutado al finalizar exitosamente la generación 3D.
   * Proporciona la URL pre-firmada del GLB y el ID del trabajo.
   */
  onGenerationComplete: (glbUrl: string, jobId: string) => void;
}

interface JobState {
  status: string;
  progress: number;
  error?: string | null;
  jobId: string | null;
}

export const ImageUploader: React.FC<ImageUploaderProps> = ({ onGenerationComplete }) => {
  const [file, setFile] = useState<File | null>(null);
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

  const gatewayHttpUrl = import.meta.env.PUBLIC_GATEWAY_HTTP_URL || 'http://localhost:8080';

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
    if (selectedFile.type.startsWith('image/')) {
      setFile(selectedFile);
      setJobState({ status: 'idle', progress: 0, error: null, jobId: null });
      setTerminalLogs([]);
      addLog(`Archivo seleccionado: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`);
    } else {
      addLog("ERROR: El archivo seleccionado debe ser una imagen (PNG/JPG).");
    }
  };

  const triggerFileSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const start3DGeneration = async () => {
    if (!file) return;

    setUploading(true);
    setTerminalLogs([]);
    addLog("Iniciando Pipeline A: Imagen 2D a Malla GLB...");
    addLog("Preparando payload multipart...");

    const formData = new FormData();
    formData.append('image', file);

    try {
      addLog(`Subiendo archivo al API Gateway en ${gatewayHttpUrl}/api/generate-3d...`);
      const res = await fetch(`${gatewayHttpUrl}/api/generate-3d`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `HTTP error! status: ${res.status}`);
      }

      const data = await res.json();
      const jobId = data.job_id;

      addLog(`¡Subida exitosa! Job ID asignado: ${jobId}`);
      addLog(`Estado inicial registrado: ${data.status}`);
      
      setJobState({
        status: 'queued',
        progress: 0,
        error: null,
        jobId
      });

      // Empezar polling inteligente cada 3 segundos
      startPolling(jobId);

    } catch (err: any) {
      addLog(`ERROR CRÍTICO DE SUBIDA: ${err.message}`);
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
    addLog("Inicializando listener de polling interactivo (intervalo: 3000ms)...");
    
    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(`${gatewayHttpUrl}/api/jobs/${jobId}`);
        if (!res.ok) {
          throw new Error(`Error en HTTP polling: ${res.status}`);
        }

        const data = await res.json();
        
        // Mapeo dinámico de estados del worker Celery
        const status = data.status;
        const progress = data.progress || 0;
        
        addLog(`Consulta de progreso: [${status.toUpperCase()}] | Progreso: ${progress}%`);

        if (status === 'done' || status === 'success') {
          clearInterval(intervalId);
          addLog("¡PROCESAMIENTO FINALIZADO CON ÉXITO!");
          addLog(`Generando Presigned URL para descarga segura...`);
          addLog(`Modelo GLB cargado correctamente.`);

          setJobState({
            status: 'done',
            progress: 100,
            error: null,
            jobId
          });
          setUploading(false);
          
          // Notificar al padre la URL del GLB para cargarlo en Three.js
          onGenerationComplete(data.result_url, jobId);

        } else if (status === 'error' || status === 'failed') {
          clearInterval(intervalId);
          const errMsg = data.error_message || "Fallo en la inferencia del modelo 3DGS o auto-rigging.";
          addLog(`[PIPELINE_ERROR] ${errMsg}`);
          setJobState({
            status: 'error',
            progress: progress,
            error: errMsg,
            jobId
          });
          setUploading(false);
        } else {
          // Actualizar estado en progreso (queued, processing, etc.)
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

  return (
    <div className="panel-terminal" style={{ width: '100%', maxWidth: '480px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ fontSize: '0.85rem', color: '#00f07f', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>
        &gt; PIPELINE_A: IMAGE_TO_3D
      </h3>

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
          cursor: uploading ? 'not-allowed' : 'pointer',
          transition: 'all 0.2s ease',
          pointerEvents: uploading ? 'none' : 'auto'
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleChange}
          style={{ display: 'none' }}
        />
        
        {file ? (
          <div>
            <div style={{ color: '#f5f5f5', fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.5rem', wordBreak: 'break-all' }}>
              {file.name}
            </div>
            <div style={{ color: '#8e8e8e', fontSize: '0.65rem' }}>
              Haz clic para reemplazar la imagen del personaje
            </div>
          </div>
        ) : (
          <div>
            <div style={{ color: '#8e8e8e', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
              Arrastra una imagen de personaje aquí
            </div>
            <div style={{ color: '#00f07f', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 'bold' }}>
              o busca en tu dispositivo
            </div>
          </div>
        )}
      </div>

      {file && !uploading && jobState.status === 'idle' && (
        <button
          className="btn-retro"
          onClick={start3DGeneration}
          style={{ width: '100%', textTransform: 'uppercase' }}
        >
          COMPILAR AVATAR 3D
        </button>
      )}

      {/* Monitor de Progreso */}
      {jobState.status !== 'idle' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', fontFamily: 'var(--font-mono)' }}>
            <span style={{ color: '#8e8e8e' }}>JOB_STATUS: <span style={{ color: jobState.status === 'error' ? '#ff3333' : '#00f07f', fontWeight: 'bold' }}>{jobState.status.toUpperCase()}</span></span>
            <span style={{ color: '#00f07f' }}>{jobState.progress}%</span>
          </div>
          
          {/* Barra de progreso cyberpunk */}
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
                color: log.includes('ERROR') ? '#ff3333' : log.includes('SUCCESS') || log.includes('FINALIZADO') ? '#00f07f' : '#d5d5d5',
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
