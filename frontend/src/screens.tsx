import { queryString, request, utcStamp } from "./api"
import type { Consent, FarmerProfile, PriceList, SaleWindow } from "./types"
import { Field, Form, Notice, useSubmit } from "./ui"
import { useState } from "react"

const PURPOSE = "Market Linkage and Profile Verification"

export function Prices() {
  const { error, pending, run } = useSubmit()
  const [result, setResult] = useState<PriceList | null>(null)

  return (
    <section>
      <Form
        title="Mandi prices"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          void run(async () => {
            const body = await request<PriceList>(
              `/api/v1/prices${queryString({
                commodity: String(data.get("commodity") ?? ""),
                state: String(data.get("state") ?? ""),
                district: String(data.get("district") ?? ""),
                market: String(data.get("market") ?? ""),
              })}`,
            )
            setResult(body)
          })
        }}
      >
        <Field label="Commodity" name="commodity" />
        <Field label="State" name="state" />
        <Field label="District" name="district" />
        <Field label="Market" name="market" />
        <button type="submit" disabled={pending}>
          {pending ? "Looking up…" : "Look up prices"}
        </button>
      </Form>
      <Notice error={error}>
        {result && result.data.length === 0 ? <p>No prices match that filter.</p> : null}
        {result && result.data.length > 0 ? (
          <div className="table-wrap">
            <table>
              <caption>{result.meta.count} matching rows</caption>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Market</th>
                  <th>Commodity</th>
                  <th>Variety</th>
                  <th>Grade</th>
                  <th>Min</th>
                  <th>Max</th>
                  <th>Modal</th>
                </tr>
              </thead>
              <tbody>
                {result.data.map((row) => (
                  <tr key={`${row.arrival_date}-${row.market}-${row.commodity}-${row.variety}-${row.grade}`}>
                    <td>{row.arrival_date}</td>
                    <td>
                      {row.market}
                      <span className="muted">
                        {row.district}, {row.state}
                      </span>
                    </td>
                    <td>{row.commodity}</td>
                    <td>{row.variety || "—"}</td>
                    <td>{row.grade || "—"}</td>
                    <td>{row.min_price_inr_per_quintal}</td>
                    <td>{row.max_price_inr_per_quintal}</td>
                    <td>{row.modal_price_inr_per_quintal}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Notice>
    </section>
  )
}

export function SaleWindowScreen() {
  const { error, pending, run } = useSubmit()
  const [result, setResult] = useState<SaleWindow | null>(null)

  return (
    <section>
      <Form
        title="Sale window"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          void run(async () => {
            const body = await request<SaleWindow>(
              `/api/v1/prices/sale-window${queryString({
                commodity: String(data.get("commodity") ?? ""),
                state: String(data.get("state") ?? ""),
                market: String(data.get("market") ?? ""),
                horizon_days: String(data.get("horizon_days") ?? "14"),
                storage_cost_per_quintal_per_day: String(data.get("storage_cost") ?? "0"),
              })}`,
            )
            setResult(body)
          })
        }}
      >
        <p className="lede">
          A straight-line reading of stored modal prices. Store only when the projected rise
          covers the storage cost.
        </p>
        <Field label="Commodity" name="commodity" required />
        <Field label="State" name="state" />
        <Field label="Market" name="market" />
        <Field label="Horizon in days (7–21)" name="horizon_days" defaultValue="14" type="number" required />
        <Field label="Storage cost per quintal per day" name="storage_cost" defaultValue="0" type="number" />
        <button type="submit" disabled={pending}>
          {pending ? "Calculating…" : "Recommend"}
        </button>
      </Form>
      <Notice error={error}>
        {result ? (
          <article className={result.recommendation === "store" ? "decision store" : "decision sell"}>
            <p className="decision-label">{result.recommendation}</p>
            <p>{result.reason}</p>
            <dl>
              <div>
                <dt>Latest modal</dt>
                <dd>{result.latest_modal_price_inr_per_quintal ?? "—"}</dd>
              </div>
              <div>
                <dt>Projected modal</dt>
                <dd>{result.projected_modal_price_inr_per_quintal ?? "—"}</dd>
              </div>
              <div>
                <dt>Storage cost</dt>
                <dd>{result.storage_cost_inr_per_quintal}</dd>
              </div>
              <div>
                <dt>Observations</dt>
                <dd>{result.observations}</dd>
              </div>
            </dl>
          </article>
        ) : null}
      </Notice>
    </section>
  )
}

export function ConsentScreen() {
  const grant = useSubmit()
  const withdraw = useSubmit()
  const lookup = useSubmit()
  const [artifact, setArtifact] = useState<Consent | null>(null)

  return (
    <section>
      <Form
        title="Record consent"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          void grant.run(async () => {
            const body = await request<Consent>("/api/v1/consents", {
              method: "POST",
              body: JSON.stringify({
                artifact_id: String(data.get("artifact_id") ?? "").trim(),
                farmer_id: String(data.get("farmer_id") ?? "").trim(),
                purpose: PURPOSE,
                attributes: ["profile", "land"],
                created_at: utcStamp(String(data.get("created_at") ?? "")),
                expires_at: utcStamp(String(data.get("expires_at") ?? "")),
                signature: String(data.get("signature") ?? "").trim(),
              }),
            })
            setArtifact(body)
          })
        }}
      >
        <p className="lede">
          The consent manager signs the artifact. Paste that signature here. This desk does not
          hold the signing secret.
        </p>
        <p className="purpose">{PURPOSE}</p>
        <Field label="Artifact id" name="artifact_id" required />
        <Field label="Farmer id" name="farmer_id" required />
        <Field label="Created (UTC)" name="created_at" defaultValue="2026-09-21T00:00:00Z" required />
        <Field label="Expires (UTC)" name="expires_at" defaultValue="2026-10-21T00:00:00Z" required />
        <Field label="Signature" name="signature" required />
        <button type="submit" disabled={grant.pending}>
          {grant.pending ? "Recording…" : "Record consent"}
        </button>
      </Form>
      <Notice error={grant.error} />
      <Form
        title="Withdraw consent"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          const artifactId = String(data.get("artifact_id") ?? "").trim()
          void withdraw.run(async () => {
            const body = await request<Consent>(`/api/v1/consents/${encodeURIComponent(artifactId)}/withdrawals`, {
              method: "POST",
              body: JSON.stringify({ signature: String(data.get("signature") ?? "").trim() }),
            })
            setArtifact(body)
          })
        }}
      >
        <Field label="Artifact id" name="artifact_id" required />
        <Field label="Withdrawal signature" name="signature" required />
        <button type="submit" disabled={withdraw.pending}>
          {withdraw.pending ? "Withdrawing…" : "Withdraw"}
        </button>
      </Form>
      <Notice error={withdraw.error} />
      <Form
        title="Look up an artifact"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          const artifactId = String(data.get("artifact_id") ?? "").trim()
          void lookup.run(async () => {
            setArtifact(await request<Consent>(`/api/v1/consents/${encodeURIComponent(artifactId)}`))
          })
        }}
      >
        <Field label="Artifact id" name="artifact_id" required />
        <button type="submit" disabled={lookup.pending}>
          {lookup.pending ? "Looking up…" : "Look up"}
        </button>
      </Form>
      <Notice error={lookup.error}>
        {artifact ? <ConsentCard consent={artifact} /> : null}
      </Notice>
    </section>
  )
}

function ConsentCard({ consent }: { consent: Consent }) {
  return (
    <article className="card">
      <p className={consent.status === "active" ? "status active" : "status withdrawn"}>{consent.status}</p>
      <dl>
        <div>
          <dt>Artifact</dt>
          <dd>{consent.artifact_id}</dd>
        </div>
        <div>
          <dt>Farmer</dt>
          <dd>{consent.farmer_id}</dd>
        </div>
        <div>
          <dt>Purpose</dt>
          <dd>{consent.purpose}</dd>
        </div>
        <div>
          <dt>Attributes</dt>
          <dd>{consent.attributes.join(", ")}</dd>
        </div>
      </dl>
    </article>
  )
}

export function ProfileScreen() {
  const resolve = useSubmit()
  const lookup = useSubmit()
  const [profile, setProfile] = useState<FarmerProfile | null>(null)

  return (
    <section>
      <Form
        title="Fetch a profile"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          void resolve.run(async () => {
            const body = await request<FarmerProfile>("/api/v1/farmers/profile", {
              method: "POST",
              body: JSON.stringify({
                farmer_id: String(data.get("farmer_id") ?? "").trim(),
                state_lgd_code: String(data.get("state_lgd_code") ?? "").trim(),
                consent_artifact_id: String(data.get("consent_artifact_id") ?? "").trim(),
              }),
            })
            setProfile(body)
          })
        }}
      >
        <p className="lede">The registry is called only when an active consent artifact covers this farmer.</p>
        <Field label="Farmer id" name="farmer_id" required />
        <Field label="State code" name="state_lgd_code" required />
        <Field label="Consent artifact id" name="consent_artifact_id" required />
        <button type="submit" disabled={resolve.pending}>
          {resolve.pending ? "Fetching…" : "Fetch profile"}
        </button>
      </Form>
      <Notice error={resolve.error} />
      <Form
        title="Open a stored profile"
        onSubmit={(event) => {
          const data = new FormData(event.currentTarget)
          const farmerId = String(data.get("farmer_id") ?? "").trim()
          void lookup.run(async () => {
            setProfile(await request<FarmerProfile>(`/api/v1/farmers/${encodeURIComponent(farmerId)}`))
          })
        }}
      >
        <Field label="Farmer id" name="farmer_id" required />
        <button type="submit" disabled={lookup.pending}>
          {lookup.pending ? "Opening…" : "Open"}
        </button>
      </Form>
      <Notice error={lookup.error}>{profile ? <ProfileCard profile={profile} /> : null}</Notice>
    </section>
  )
}

function ProfileCard({ profile }: { profile: FarmerProfile }) {
  return (
    <article className="card">
      <h3>{profile.display_name}</h3>
      <p className="muted">
        {profile.farmer_id} · state {profile.state_lgd_code}
      </p>
      {profile.parcels.length === 0 ? <p>No land parcels on this profile.</p> : null}
      <ul className="parcels">
        {profile.parcels.map((parcel) => (
          <li key={parcel.farm_id}>
            <strong>{parcel.farm_id}</strong>
            {parcel.area_hectares ? <span> · {parcel.area_hectares} ha</span> : null}
            {parcel.crops.length > 0 ? (
              <span className="muted">{parcel.crops.map((crop) => `${crop.commodity} (${crop.season})`).join(", ")}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </article>
  )
}
