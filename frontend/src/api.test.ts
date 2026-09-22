import { describe, expect, it } from "vitest"
import { queryString, utcStamp } from "./api"

describe("queryString", () => {
  it("omits blank filters", () => {
    expect(queryString({ commodity: " Onion ", state: "  ", limit: 25 })).toBe(
      "?commodity=Onion&limit=25",
    )
  })

  it("returns an empty string when every filter is blank", () => {
    expect(queryString({ commodity: "", state: undefined })).toBe("")
  })
})

describe("utcStamp", () => {
  it("adds a Z when the consent manager timestamp has no zone", () => {
    expect(utcStamp("2026-09-21T00:00:00")).toBe("2026-09-21T00:00:00Z")
    expect(utcStamp("2026-09-21T00:00:00Z")).toBe("2026-09-21T00:00:00Z")
  })
})
