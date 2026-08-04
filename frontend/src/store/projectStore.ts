import { create } from 'zustand'

export type ChatRole = 'user' | 'assistant' | 'log' | 'skill_done' | 'reasoning'
export type WsStatus = 'idle' | 'connected' | 'running'

export interface ChatMessage {
  id: string
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

export interface ProjectListItem {
  name: string
  has_engineer?: boolean
  tracks_count?: number
  updated?: number
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
  projects: ProjectListItem[]
  currentProject: string | null
  projectData: ProjectData | null
  chat: ChatMessage[]
  wsStatus: WsStatus
  audioPath: string | null
  // actions
  loadProjects: (projects: ProjectListItem[]) => void
  selectProject: (name: string | null) => void
  loadProjectData: (data: ProjectData | null) => void
  addChat: (message: Omit<ChatMessage, 'id'>) => void
  appendChat: (id: string, text: string) => void  // 流式追加到同一条消息
  streamReasoning: (text: string, done: boolean) => void  // 思考过程流式: 首次创建,后续追加,done结束
  sendChat: (msg: string, audioPath?: string) => void
  setWsStatus: (status: WsStatus) => void
  setAudioPath: (path: string | null) => void
}

let _msgSeq = 0
const newId = () => `m${Date.now()}_${_msgSeq++}`
let _activeReasoningId: string | null = null

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
    chat: [...state.chat, { ...message, id: newId() }]
  })),

  appendChat: (id, text) => set((state) => ({
    chat: state.chat.map((m) => (m.id === id ? { ...m, msg: m.msg + text } : m))
  })),

  streamReasoning: (text, done) => set((state) => {
    if (!_activeReasoningId) {
      // 首次: 创建 reasoning 消息
      const id = newId()
      _activeReasoningId = id
      return { chat: [...state.chat, { id, role: 'reasoning' as ChatRole, msg: text }] }
    }
    // 后续: 追加
    const chat = state.chat.map((m) =>
      m.id === _activeReasoningId ? { ...m, msg: m.msg + text } : m
    )
    if (done) _activeReasoningId = null
    return { chat }
  }),

  sendChat: (msg, audioPath) => {
    set((state) => ({
      chat: [...state.chat, { id: newId(), role: 'user' as ChatRole, msg, files: audioPath ? [audioPath] : undefined }]
    }))
  },

  setWsStatus: (status) => set({ wsStatus: status }),

  setAudioPath: (path) => set({ audioPath: path }),
}))