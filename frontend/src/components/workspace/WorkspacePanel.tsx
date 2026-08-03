import { useEffect, useState } from 'react'
import { useProjectStore } from '../../store/projectStore'
import { listProjects, getProject } from '../../services/api'

export default function WorkspacePanel() {
  const { projects, currentProject, projectData, loadProjects, selectProject, loadProjectData } = useProjectStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // load project list on mount
  useEffect(() => {
    listProjects()
      .then(loadProjects)
      .catch(() => {
        // ignore if backend not running
      })
  }, [loadProjects])

  const handleSelectProject = async (name: string) => {
    selectProject(name)
    setLoading(true)
    setError(null)
    try {
      const data = await getProject(name)
      loadProjectData(data)
    } catch (err) {
      setError('加载工程失败')
      loadProjectData(null)
    } finally {
      setLoading(false)
    }
  }

  const handleNewProject = () => {
    const name = prompt('输入新工程名称:')
    if (name) {
      selectProject(name)
      loadProjectData({ name })
      loadProjects([...projects, { name }])
    }
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Project selector */}
      <div className="flex items-center gap-3 p-3 border-b bg-gray-50">
        <select
          value={currentProject || ''}
          onChange={(e) => handleSelectProject(e.target.value)}
          className="flex-1 border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          <option value="">-- 选择工程 --</option>
          {projects.map((p) => (
            <option key={p.name} value={p.name}>{p.name}</option>
          ))}
        </select>
        <button
          onClick={handleNewProject}
          className="px-3 py-1.5 bg-green-500 text-white rounded-md text-sm hover:bg-green-600 transition"
        >
          新建工程
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading && (
          <div className="text-center text-gray-400 mt-10">加载中...</div>
        )}
        {!loading && !currentProject && !projectData && (
          <div className="text-center text-gray-400 mt-10">
            <p className="text-lg">请先选择或创建工程</p>
            <p className="text-sm mt-2">使用左侧对话或上方按钮操作</p>
          </div>
        )}
        {!loading && error && (
          <div className="text-center text-red-400 mt-10">{error}</div>
        )}
        {!loading && projectData && (
          <ProjectContent data={projectData} />
        )}
      </div>
    </div>
  )
}

function ProjectContent({ data }: { data: any }) {
  // 后端 song_engineer.json: basic_info 嵌套, sections 项有 name/chords/bars, tracks 项有 name/role/status/type
  const basic = data.basic_info || data.basic || data.meta || {}
  const bpm = basic.bpm || data.bpm
  const key = basic.key || basic.arranged_key || data.key
  const style = basic.style || data.style
  const mood = basic.mood || data.mood
  const sections = data.sections || []
  const tracks = data.tracks || []
  return (
    <div className="space-y-4">
      {/* Basic Info Card */}
      <div className="border rounded-lg p-4">
        <h3 className="font-medium text-gray-700 mb-3">基本信息</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <InfoItem label="调性" value={key || '-'} />
          <InfoItem label="BPM" value={bpm || '-'} />
          <InfoItem label="风格" value={style || '-'} />
          <InfoItem label="情绪" value={mood || '-'} />
        </div>
      </div>

      {/* Section Table */}
      {sections.length > 0 && (
        <div className="border rounded-lg p-4">
          <h3 className="font-medium text-gray-700 mb-3">段落与和弦</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 font-medium text-gray-600">段落</th>
                <th className="text-left py-2 font-medium text-gray-600">小节</th>
                <th className="text-left py-2 font-medium text-gray-600">和弦</th>
              </tr>
            </thead>
            <tbody>
              {sections.map((sec: any, idx: number) => (
                <tr key={idx} className="border-b last:border-0">
                  <td className="py-2">{sec.name || sec.section}</td>
                  <td className="py-2 text-gray-600">{sec.bars || sec.bar || '-'}</td>
                  <td className="py-2 text-gray-600">{sec.chords || sec.chord || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Track List */}
      {tracks.length > 0 && (
        <div className="border rounded-lg p-4">
          <h3 className="font-medium text-gray-700 mb-3">分轨列表</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 font-medium text-gray-600">名称</th>
                <th className="text-left py-2 font-medium text-gray-600">角色</th>
                <th className="text-left py-2 font-medium text-gray-600">状态</th>
                <th className="text-left py-2 font-medium text-gray-600">类型</th>
              </tr>
            </thead>
            <tbody>
              {tracks.map((track: any, idx: number) => (
                <tr key={idx} className="border-b last:border-0">
                  <td className="py-2">{track.name}</td>
                  <td className="py-2 text-gray-600">{track.role}</td>
                  <td className="py-2">
                    <StatusBadge status={track.status} />
                  </td>
                  <td className="py-2 text-gray-600">{track.type || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function InfoItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <span className="text-gray-500">{label}: </span>
      <span className="font-medium">{value}</span>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    done: 'bg-green-100 text-green-700',
    pending: 'bg-yellow-100 text-yellow-700',
    running: 'bg-blue-100 text-blue-700',
    error: 'bg-red-100 text-red-700',
  }
  const cls = colors[status?.toLowerCase()] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>
      {status || 'unknown'}
    </span>
  )
}