const BASE_URL = 'http://127.0.0.1:8000'

function encodeName(name: string): string {
  return encodeURIComponent(name)
}

export async function listProjects(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/api/projects`)
  if (!res.ok) throw new Error(`listProjects failed: ${res.status}`)
  return res.json()
}

export async function getProject(name: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${encodeName(name)}`)
  if (!res.ok) throw new Error(`getProject failed: ${res.status}`)
  return res.json()
}

export async function getTrack(name: string, tid: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/project/${encodeName(name)}/track/${encodeName(tid)}`)
  if (!res.ok) throw new Error(`getTrack failed: ${res.status}`)
  return res.json()
}

export async function saveTrack(name: string, tid: string, md: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/project/${encodeName(name)}/track/${encodeName(tid)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markdown: md }),
  })
  if (!res.ok) throw new Error(`saveTrack failed: ${res.status}`)
}

export async function uploadAudio(file: File): Promise<{ path: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/api/audio/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`uploadAudio failed: ${res.status}`)
  return res.json()
}

export async function listSkills(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/api/skills`)
  if (!res.ok) throw new Error(`listSkills failed: ${res.status}`)
  return res.json()
}

export async function runSkill(tool: string, args: Record<string, any>): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/skill/${encodeName(tool)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  if (!res.ok) throw new Error(`runSkill failed: ${res.status}`)
}