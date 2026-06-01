import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface AvatarItem {
  id: string;
  name: string;
  url: string;
  createdAt: number;
}

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
  /**
   * Colección de avatares creados y nombrados en esta sesión.
   */
  avatarsList: AvatarItem[];

  // Acciones para actualizar el estado global
  setAvatar: (url: string, jobId: string) => void;
  setVideo: (url: string, jobId: string) => void;
  addAvatar: (avatar: AvatarItem) => void;
  resetSession: () => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      activeAvatarUrl: null,
      avatarJobId: null,
      renderedVideoUrl: null,
      videoJobId: null,
      avatarsList: [],

      setAvatar: (url, jobId) => set({
        activeAvatarUrl: url,
        avatarJobId: jobId
      }),

      setVideo: (url, jobId) => set({
        renderedVideoUrl: url,
        videoJobId: jobId
      }),

      addAvatar: (avatar) => set((state) => {
        const filtered = state.avatarsList.filter(a => a.id !== avatar.id);
        return {
          avatarsList: [...filtered, avatar],
          activeAvatarUrl: avatar.url,
          avatarJobId: avatar.id
        };
      }),

      resetSession: () => set({
        activeAvatarUrl: null,
        avatarJobId: null,
        renderedVideoUrl: null,
        videoJobId: null,
        avatarsList: []
      })
    }),
    {
      name: 'biorender-session-store',
      storage: typeof window !== 'undefined' ? createJSONStorage(() => localStorage) : undefined,
    }
  )
);

