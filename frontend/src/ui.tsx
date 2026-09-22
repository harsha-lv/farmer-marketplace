import { useState, type FormEvent, type ReactNode } from "react"
import { ApiError } from "./api"

export function useSubmit() {
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function run(task: () => Promise<void>) {
    setPending(true)
    setError(null)
    try {
      await task()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong")
    } finally {
      setPending(false)
    }
  }

  return { error, pending, run }
}

export function Form({
  title,
  onSubmit,
  children,
}: {
  title: string
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  children: ReactNode
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(event)
      }}
    >
      <h2>{title}</h2>
      {children}
    </form>
  )
}

export function Field({
  label,
  name,
  defaultValue = "",
  required = false,
  type = "text",
}: {
  label: string
  name: string
  defaultValue?: string
  required?: boolean
  type?: string
}) {
  return (
    <label>
      {label}
      <input name={name} type={type} defaultValue={defaultValue} required={required} />
    </label>
  )
}

export function Notice({ error, children }: { error: string | null; children?: ReactNode }) {
  return (
    <>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {children}
    </>
  )
}
