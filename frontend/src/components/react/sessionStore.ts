import { create } from 'zustand';

interface SessionState {
  /**
   * URL pre-firmada (S3) del avatar GLB activo actualmente en la sesión.
   */
  activeAvatarUrl: string | null;
  /**
   * UUID del Job que compiló el avatar activo.
   */
  avatarJobId: string | null;
  /**
   * URL pre-firmada del video MP4 renderizado por Blender Headless.
   */
  renderedVideoUrl: string | null;
  /**
   * UUID del Job de procesamiento y retargeting de video.
   */
  videoJobId: string | null;

  // Acciones para actualizar el estado global
  setAvatar: (url: string, jobId: string) => void;
  setVideo: (url: string, jobId: string) => void;
  resetSession: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  activeAvatarUrl: null,
  avatarJobId: null,
  renderedVideoUrl: null,
  videoJobId: null,

  setAvatar: (url, jobId) => set({
    activeAvatarUrl: url,
    avatarJobId: jobId
  }),

  setVideo: (url, jobId) => set({
    renderedVideoUrl: url,
    videoJobId: jobId
  }),

  resetSession: () => set({
    activeAvatarUrl: null,
    avatarJobId: null,
    renderedVideoUrl: null,
    videoJobId: null
  })
}));
