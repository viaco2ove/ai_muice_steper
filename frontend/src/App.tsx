import ChatPanel from './components/chat/ChatPanel'
import WorkspacePanel from './components/workspace/WorkspacePanel'
import { useProjectStore } from './store/projectStore'

export default function App() {
  const { currentProject, wsStatus } = useProjectStore()

  const statusColor = {
    idle: 'bg-gray-400',
    connected: 'bg-green-500',
    running: 'bg-yellow-500',
  }[wsStatus]

  const statusText = {
    idle: '未连接',
    connected: '已连接',
    running: '运行中',
  }[wsStatus]

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="h-12 flex items-center justify-between px-4 bg-gray-800 text-white shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="font-semibold">AI音乐工程工作台</h1>
          {currentProject && (
            <span className="text-sm text-gray-300">| {currentProject}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${statusColor} animate-pulse`} />
          <span className="text-xs text-gray-300">{statusText}</span>
        </div>
      </header>

      {/* Main content: left 40% chat, right 60% workspace */}
      <main className="flex-1 flex min-h-0">
        <div className="w-[40%] border-r">
          <ChatPanel />
        </div>
        <div className="w-[60%]">
          <WorkspacePanel />
        </div>
      </main>
    </div>
  )
}