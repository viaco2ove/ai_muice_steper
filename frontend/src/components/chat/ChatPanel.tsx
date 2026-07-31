import React, { useState, useRef, useEffect } from 'react'
import { useProjectStore } from '../../store/projectStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import { uploadAudio } from '../../services/api'

export default function ChatPanel() {
  const { chat, audioPath, setAudioPath } = useProjectStore()
  const { sendChat } = useWebSocket()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat])

  const handleSend = () => {
    if (!input.trim()) return
    sendChat(input, audioPath || undefined)
    setInput('')
    setAudioPath(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const result = await uploadAudio(file)
      setAudioPath(result.path)
      setInput((prev) => prev + ` [已上传音频: ${file.name}]`)
    } catch (err) {
      console.error('Upload failed:', err)
    }
    // reset input
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleRecord = () => {
    // Placeholder: 录音功能待实现
    console.log('Record clicked (placeholder)')
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Top toolbar */}
      <div className="flex gap-2 p-3 border-b bg-white">
        <button
          onClick={handleRecord}
          className="px-3 py-1.5 bg-red-500 text-white rounded-md text-sm hover:bg-red-600 transition"
        >
          录音
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="px-3 py-1.5 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 transition"
        >
          上传音频
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*"
          className="hidden"
          onChange={handleFileUpload}
        />
        {audioPath && (
          <span className="text-xs text-gray-500 self-center ml-2 truncate max-w-[150px]">
            已选: {audioPath.split(/[/\\]/).pop()}
          </span>
        )}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {chat.length === 0 && (
          <div className="text-center text-gray-400 mt-10">
            <p>开始对话吧！</p>
            <p className="text-sm mt-1">AI会帮你完成音乐工程</p>
          </div>
        )}
        {chat.map((item, idx) => (
          <MessageBubble key={idx} message={item} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-3 border-t bg-white">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Enter发送)"
            className="flex-1 resize-none border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-4 py-2 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: { role: string; msg: string; files?: string[] } }) {
  const { role, msg, files } = message

  if (role === 'log') {
    return (
      <div className="flex items-start gap-2">
        <span className="text-xs text-gray-400 mt-1 shrink-0">[LOG]</span>
        <p className="text-xs text-gray-400">{msg}</p>
      </div>
    )
  }

  if (role === 'skill_done') {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-3">
        <div className="flex items-center gap-2 text-green-700">
          <span className="text-lg">&#10003;</span>
          <span className="font-medium">技能执行完成</span>
        </div>
        {msg && <p className="text-sm text-green-600 mt-1">{msg}</p>}
        {files && files.length > 0 && (
          <div className="mt-2 text-xs text-green-600">
            产物: {files.map((f) => f.split(/[/\\]/).pop()).join(', ')}
          </div>
        )}
      </div>
    )
  }

  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-500 text-white rounded-lg px-4 py-2 max-w-[80%]">
          <p className="text-sm whitespace-pre-wrap">{msg}</p>
        </div>
      </div>
    )
  }

  // assistant
  return (
    <div className="flex justify-start">
      <div className="bg-white border rounded-lg px-4 py-2 max-w-[80%] shadow-sm">
        <p className="text-sm whitespace-pre-wrap">{msg}</p>
      </div>
    </div>
  )
}