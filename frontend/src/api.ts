export class ApiError extends Error {
  status: number

  constructor(status: number, title: string) {
    super(title)
    this.status = status
  }
}

export function apiBase(): string {
  return import.meta.env.VITE_API_BASE ?? ""
}

export function utcStamp(value: string): string {
  const text = value.trim()
  if (text.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(text)) return text
  return `${text}Z`
}

export function queryString(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined) continue
    const text = String(value).trim()
    if (text === "") continue
    params.set(key, text)
  }
  const query = params.toString()
  return query ? `?${query}` : ""
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: {
        accept: "application/json",
        ...(init?.body ? { "content-type": "application/json" } : {}),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError(0, "The API is not reachable")
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const title = body?.errors?.[0]?.title
    throw new ApiError(response.status, typeof title === "string" ? title : "Request failed")
  }
  return response.json() as Promise<T>
}
