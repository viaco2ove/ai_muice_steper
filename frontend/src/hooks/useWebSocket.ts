import { useEffect, useRef, useCallback } from 'react'
import { useProjectStore } from '../store/projectStore'
import { getProject } from '../services/api'

const WS_URL = 'ws://127.0.0.1:8000/ws/chat'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const manualCloseRef = useRef(false)
  const storeRef = useRef(useProjectStore.getState())

  // 保持 store 引用最新（不放进 connect 依赖，避免重连）
  useEffect(() => {
    const unsub = useProjectStore.subscribe((s) => {
      storeRef.current = s
    })
    return unsub
  }, [])

  const handleMessage = useCallback((data: any) => {
    const s = storeRef.current
    const type = data.type
    // 后端字段: log/skill_done 用 msg, text 用 msg, project_updated 用 project(工程名)
    switch (type) {
      case 'pong':
        break
      case 'reasoning':
        // 流式思考过程: 后端发 {msg:text, done:bool}
        s.streamReasoning(data.msg || '', !!data.done)
        break
      case 'log':
        s.addChat({ role: 'log', msg: (data.tool ? `[${data.tool}] ` : '') + (data.msg || '') })
        break
      case 'text':
        s.addChat({ role: 'assistant', msg: data.msg || '' })
        break
      case 'llm_raw':
        s.addChat({ role: 'log', msg: '[LLM] ' + (data.msg || '').slice(0, 200) })
        break
      case 'skill_done':
        s.addChat({ role: 'skill_done', msg: `${data.tool || ''} ${data.status === 'ok' ? '✓' : '✗'}`, files: data.files })
        break
      case 'chain_start':
        s.addChat({ role: 'log', msg: `▶ 任务链: ${(data.tools || []).join(' → ')}` })
        s.setWsStatus('running')
        break
      case 'chain_done':
        s.addChat({ role: 'log', msg: `■ 完成: ok=${data.ok} fail=${data.fail}` })
        s.setWsStatus('connected')
        break
      case 'project_updated':
        // 后端发工程名, 重新拉取工程数据
        if (data.project) {
          getProject(data.project)
            .then((d) => s.loadProjectData(d))
            .catch(() => {})
        }
        break
      case 'error':
        s.addChat({ role: 'log', msg: '❌ ' + (data.msg || '') })
        break
      default:
        console.log('[WS] Unknown msg:', type, data)
    }
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return

    manualCloseRef.current = false
    try {
      const ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        console.log('[WS] Connected')
        storeRef.current.setWsStatus('connected')
      }

      ws.onmessage = (event) => {
        try {
          handleMessage(JSON.parse(event.data))
        } catch (e) {
          console.error('[WS] parse failed:', e)
        }
      }

      ws.onclose = () => {
        console.log('[WS] Disconnected')
        storeRef.current.setWsStatus('idle')
        wsRef.current = null
        if (!manualCloseRef.current) {
          reconnectTimerRef.current = setTimeout(() => {
            console.log('[WS] Reconnecting...')
            connect()
          }, 2000)
        }
      }

      ws.onerror = () => {
        // onclose 会紧跟触发, 这里不额外处理避免重复
      }

      wsRef.current = ws
    } catch (e) {
      console.error('[WS] Connection failed:', e)
    }
  }, [handleMessage])

  const sendChat = useCallback((msg: string, audioPath?: string, project?: string) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Not connected, cannot send')
      return false
    }
    const payload: any = { type: 'chat', msg }
    if (audioPath) payload.audio_path = audioPath
    if (project) payload.project = project
    wsRef.current.send(JSON.stringify(payload))
    return true
  }, [])

  useEffect(() => {
    connect()
    return () => {
      manualCloseRef.current = true
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { sendChat }
}