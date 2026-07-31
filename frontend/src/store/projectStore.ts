import { create } from 'zustand'

export type ChatRole = 'user' | 'assistant' | 'log' | 'skill_done'
export type WsStatus = 'idle' | 'connected' | 'running'

export interface ChatMessage {
  role: ChatRole
  msg: string
  files?: string[]
}

export interface TrackInfo {
  name: string
  role: string
  status: string
  timbre: string
}

export interface SectionInfo {
  section: string
  chord: string
}

export interface ProjectData {
  name: string
  key?: string
  bpm?: number
  style?: string
  mood?: string
  sections?: SectionInfo[]
  tracks?: TrackInfo[]
}

interface ProjectState {
  projects: string[]
  currentProject: string | null
  projectData: ProjectData | null
  chat: ChatMessage[]
  wsStatus: WsStatus
  audioPath: string | null
  // actions
  loadProjects: (projects: string[]) => void
  selectProject: (name: string | null) => void
  loadProjectData: (data: ProjectData | null) => void
  addChat: (message: ChatMessage) => void
  sendChat: (msg: string, audioPath?: string) => void
  setWsStatus: (status: WsStatus) => void
  setAudioPath: (path: string | null) => void
}

export const useProjectStore = create<ProjectState>((set) => ({
  projects: [],
  currentProject: null,
  projectData: null,
  chat: [],
  wsStatus: 'idle',
  audioPath: null,

  loadProjects: (projects) => set({ projects }),

  selectProject: (name) => set({ currentProject: name }),

  loadProjectData: (data) => set({ projectData: data }),

  addChat: (message) => set((state) => ({
    chat: [...state.chat, message]
  })),

  sendChat: (msg, audioPath) => {
    set((state) => ({
      chat: [...state.chat, { role: 'user' as ChatRole, msg, files: audioPath ? [audioPath] : undefined }]
    }))
  },

  setWsStatus: (status) => set({ wsStatus: status }),

  setAudioPath: (path) => set({ audioPath: path }),
}))