import { useEffect, useRef, useState, useCallback } from 'react';

export interface BoneRotation {
  bone_name: string;
  quaternion: [number, number, number, number]; // [x, y, z, w]
}

export interface PoseResultMessage {
  frame_id: number;
  bone_rotations: BoneRotation[];
}

/**
 * Hook personalizado para manejar el ciclo de vida de la conexión WebSocket con el Gateway.
 * 
 * @param url URL del servidor WebSocket (ej: ws://localhost:8080/ws/live-pose).
 * @param onMessage Callback invocado al recibir un nuevo PoseResultMessage deserializado.
 * @returns Estado de conexión y método para enviar payloads.
 */
export const useWebSocket = (url: string, onMessage: (data: PoseResultMessage) => void) => {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Almacenar el callback onMessage en un ref mutable para evitar recrear
  // el loop de reconexión cuando la referencia del callback lambda cambia en cada render.
  const onMessageRef = useRef(onMessage);
  
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    // Si ya está conectado o conectándose, evitar duplicados
    if (wsRef.current && (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN)) {
      return;
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('Conectado al API Gateway WebSocket.');
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const data: PoseResultMessage = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch (err) {
        console.error('Error procesando el payload de pose:', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket cerrado. Reconectando en 3 segundos...');
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000) as unknown as number;
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      ws.close();
    };
  }, [url]); // Solo depende de la URL fija, previniendo loops infinitos

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  /**
   * Envía un mensaje JSON tipado sobre el canal WebSocket activo.
   */
  const sendMessage = useCallback((msg: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { isConnected, sendMessage };
};
