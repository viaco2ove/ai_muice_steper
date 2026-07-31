import { useEffect, useRef, useCallback } from 'react'
import { useProjectStore } from '../store/projectStore'

const WS_URL = 'ws://127.0.0.1:8000/ws/chat'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { addChat, loadProjectData, setWsStatus } = useProjectStore()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        console.log('[WS] Connected')
        setWsStatus('connected')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleMessage(data)
        } catch (e) {
          console.error('[WS] Failed to parse message:', e)
        }
      }

      ws.onclose = () => {
        console.log('[WS] Disconnected')
        setWsStatus('idle')
        // auto reconnect after 3s
        reconnectTimerRef.current = setTimeout(() => {
          console.log('[WS] Reconnecting...')
          connect()
        }, 3000)
      }

      ws.onerror = (err) => {
        console.error('[WS] Error:', err)
      }

      wsRef.current = ws
    } catch (e) {
      console.error('[WS] Connection failed:', e)
      setWsStatus('idle')
    }
  }, [addChat, loadProjectData, setWsStatus])

  const handleMessage = useCallback((data: any) => {
    const type = data.type || data.msg_type

    switch (type) {
      case 'log':
        addChat({ role: 'log', msg: data.content || data.text || '' })
        break
      case 'text':
      case 'assistant':
        addChat({ role: 'assistant', msg: data.content || data.text || '' })
        break
      case 'skill_done':
        addChat({ role: 'skill_done', msg: data.content || '技能执行完成', files: data.files })
        break
      case 'project_updated':
        if (data.project) {
          loadProjectData(data.project)
        }
        break
      case 'running':
        setWsStatus('running')
        break
      default:
        console.log('[WS] Unknown message type:', type, data)
    }
  }, [addChat, loadProjectData, setWsStatus])

  const sendChat = useCallback((msg: string, audioPath?: string, project?: string) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Not connected, cannot send')
      return
    }

    const payload: any = { type: 'chat', msg }
    if (audioPath) payload.audio_path = audioPath
    if (project) payload.project = project

    wsRef.current.send(JSON.stringify(payload))
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      wsRef.current?.close()
    }
  }, [connect])

  return { sendChat }
}