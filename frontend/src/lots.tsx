import { useState } from "react"
import { queryString, request } from "./api"
import type { Lot } from "./types"
import { Field, Form, Notice, useSubmit } from "./ui"

export function LotsScreen() {
  const create = useSubmit()
  const list = useSubmit()
  const [lots, setLots] = useState<Lot[] | null>(null)

  return (
    <section>
      <Form
        title="Record an assayed lot"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          void create.run(async () => {
            const lot = await request<Lot>("/api/v1/lots", {
              method: "POST",
              body: JSON.stringify({
                farmer_id: String(data.get("farmer_id") ?? "").trim(),
                consent_artifact_id: String(data.get("consent_artifact_id") ?? "").trim(),
                commodity: String(data.get("commodity") ?? "").trim(),
                variety: String(data.get("variety") ?? "").trim(),
                quantity_mt: String(data.get("quantity_mt") ?? "").trim(),
                grade: String(data.get("grade") ?? "").trim(),
                moisture_percent: blankNumber(data.get("moisture_percent")),
                foreign_matter_percent: blankNumber(data.get("foreign_matter_percent")),
              }),
            })
            setLots((current) => [lot, ...(current ?? []).filter((item) => item.lot_code !== lot.lot_code)])
          })
        }}
      >
        <p className="lede">
          The grade is stored once with the lot. The farmer needs a profile fetched under this consent.
        </p>
        <Field label="Farmer id" name="farmer_id" required />
        <Field label="Consent artifact id" name="consent_artifact_id" required />
        <Field label="Commodity" name="commodity" required />
        <Field label="Variety" name="variety" />
        <Field label="Quantity (metric tons)" name="quantity_mt" type="number" required />
        <Field label="Grade" name="grade" defaultValue="FAQ" required />
        <Field label="Moisture percent" name="moisture_percent" type="number" />
        <Field label="Foreign matter percent" name="foreign_matter_percent" type="number" />
        <button type="submit" disabled={create.pending}>
          {create.pending ? "Recording…" : "Record lot"}
        </button>
      </Form>
      <Notice error={create.error} />
      <Form
        title="Lots for a farmer"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          const farmerId = String(data.get("farmer_id") ?? "").trim()
          void list.run(async () => {
            const body = await request<{ data: Lot[] }>(`/api/v1/lots${queryString({ farmer_id: farmerId })}`)
            setLots(body.data)
          })
        }}
      >
        <Field label="Farmer id" name="farmer_id" required />
        <button type="submit" disabled={list.pending}>
          {list.pending ? "Loading…" : "List lots"}
        </button>
      </Form>
      <Notice error={list.error}>
        {lots && lots.length === 0 ? <p>No lots for that farmer.</p> : null}
        {lots && lots.length > 0 ? (
          <ul className="parcels">
            {lots.map((lot) => (
              <li key={lot.lot_code}>
                <strong>{lot.lot_code}</strong>
                <span>
                  {" "}
                  {lot.quantity_mt} mt {lot.commodity}
                  {lot.variety ? ` (${lot.variety})` : ""} · {lot.assay.grade}
                </span>
                <span className="muted">{lot.status}</span>
                {lot.enam_lot_id ? <span className="muted">e-NAM {lot.enam_lot_id}</span> : (
                  <RegisterLot lot={lot} onRegistered={(updated) => replaceLot(setLots, updated)} />
                )}
                {lot.warehouse_receipt_id ? (
                  <span className="muted">Receipt {lot.warehouse_receipt_id}</span>
                ) : lot.enam_lot_id ? (
                  <IssueReceipt lot={lot} onIssued={(updated) => replaceLot(setLots, updated)} />
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </Notice>
    </section>
  )
}

function replaceLot(setLots: (value: Lot[] | null | ((current: Lot[] | null) => Lot[] | null)) => void, updated: Lot) {
  setLots((current) => (current ?? []).map((item) => (item.lot_code === updated.lot_code ? updated : item)))
}

function RegisterLot({ lot, onRegistered }: { lot: Lot; onRegistered: (lot: Lot) => void }) {
  const register = useSubmit()

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        event.preventDefault()
        const data = new FormData(event.currentTarget)
        void register.run(async () => {
          const updated = await request<Lot>(`/api/v1/lots/${encodeURIComponent(lot.lot_code)}/enam-registration`, {
            method: "POST",
            body: JSON.stringify({ mandi: String(data.get("mandi") ?? "").trim() }),
          })
          onRegistered(updated)
        })
      }}
    >
      <label>
        Mandi
        <input name="mandi" required />
      </label>
      <button type="submit" disabled={register.pending}>
        {register.pending ? "Registering…" : "Register with e-NAM"}
      </button>
      <Notice error={register.error} />
    </form>
  )
}

function IssueReceipt({ lot, onIssued }: { lot: Lot; onIssued: (lot: Lot) => void }) {
  const issue = useSubmit()

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        event.preventDefault()
        const data = new FormData(event.currentTarget)
        void issue.run(async () => {
          const updated = await request<Lot>(`/api/v1/lots/${encodeURIComponent(lot.lot_code)}/warehouse-receipt`, {
            method: "POST",
            body: JSON.stringify({ warehouse_id: String(data.get("warehouse_id") ?? "").trim() }),
          })
          onIssued(updated)
        })
      }}
    >
      <label>
        Warehouse
        <input name="warehouse_id" required />
      </label>
      <button type="submit" disabled={issue.pending}>
        {issue.pending ? "Issuing…" : "Issue warehouse receipt"}
      </button>
      <Notice error={issue.error} />
    </form>
  )
}

function blankNumber(value: FormDataEntryValue | null): string | null {
  const text = String(value ?? "").trim()
  return text === "" ? null : text
}
