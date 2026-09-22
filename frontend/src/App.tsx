import { useEffect, useState } from "react"
import { ApiError, request } from "./api"
import { ConsentScreen, Prices, ProfileScreen, SaleWindowScreen } from "./screens"

const screens = [
  { id: "prices", label: "Prices" },
  { id: "sale", label: "Sale window" },
  { id: "consent", label: "Consent" },
  { id: "profile", label: "Profile" },
] as const

type ScreenId = (typeof screens)[number]["id"]

function screenFromHash(): ScreenId {
  const id = window.location.hash.replace("#", "")
  return screens.some((item) => item.id === id) ? (id as ScreenId) : "prices"
}

export function App() {
  const [screen, setScreen] = useState<ScreenId>(screenFromHash)
  const [api, setApi] = useState("Checking the API…")

  useEffect(() => {
    const sync = () => setScreen(screenFromHash())
    window.addEventListener("hashchange", sync)
    return () => window.removeEventListener("hashchange", sync)
  }, [])

  useEffect(() => {
    void request<{ status: string }>("/health")
      .then(() => setApi("API connected"))
      .catch((error: unknown) => {
        setApi(error instanceof ApiError ? error.message : "API unavailable")
      })
  }, [])

  return (
    <div className="page">
      <header>
        <div>
          <p className="eyebrow">Market desk</p>
          <h1>Prices, timing, and consent</h1>
        </div>
        <p className={api === "API connected" ? "api ok" : "api"}>{api}</p>
      </header>
      <div className="layout">
        <nav aria-label="Desk sections">
          {screens.map((item) => (
            <button
              key={item.id}
              type="button"
              className={screen === item.id ? "nav active" : "nav"}
              aria-current={screen === item.id ? "page" : undefined}
              onClick={() => {
                window.location.hash = item.id
                setScreen(item.id)
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <main>
          {screen === "prices" ? <Prices /> : null}
          {screen === "sale" ? <SaleWindowScreen /> : null}
          {screen === "consent" ? <ConsentScreen /> : null}
          {screen === "profile" ? <ProfileScreen /> : null}
        </main>
      </div>
    </div>
  )
}
