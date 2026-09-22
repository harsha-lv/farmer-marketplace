export type PriceRecord = {
  arrival_date: string
  state: string
  district: string
  market: string
  commodity: string
  variety: string
  grade: string
  min_price_inr_per_quintal: number
  max_price_inr_per_quintal: number
  modal_price_inr_per_quintal: number
}

export type PriceList = {
  data: PriceRecord[]
  meta: { limit: number; offset: number; count: number }
}

export type SaleWindow = {
  commodity: string
  recommendation: string
  reason: string
  observations: number
  latest_arrival_date: string | null
  latest_modal_price_inr_per_quintal: number | null
  average_modal_price_inr_per_quintal: number | null
  projected_modal_price_inr_per_quintal: number | null
  storage_cost_inr_per_quintal: number
  horizon_days: number
}

export type Consent = {
  artifact_id: string
  farmer_id: string
  purpose: string
  attributes: string[]
  created_at: string
  expires_at: string
  status: string
  withdrawn_at: string | null
}

export type FarmerProfile = {
  farmer_id: string
  state_lgd_code: string
  display_name: string
  consent_artifact_id: string
  fetched_at: string
  parcels: {
    farm_id: string
    area_hectares: string | null
    crops: { commodity: string; season: string }[]
  }[]
}
