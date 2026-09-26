# MittiMandi Design System Specification
**Project ID:** `6127167441810181608`  
**Origin:** Stitch Design System Explorer (`web/scripts/screens/reference.js` & `web/styles/tokens.css`)  
**Target Device Baseline:** Rural Indian Android Smartphone (360px viewport width)

---

## 1. Brand & Color Palette

### Core Palette
- **Primary:** `#36afcb` (Deep Teal / River Cyan)
  - `--primary-hover`: `#2ba0bc`
  - `--primary-active`: `#218ba4`
  - `--primary-light`: `#52c4dd`
  - `--primary-glow`: `rgba(54, 175, 203, 0.35)`
  - `--primary-subtle`: `rgba(54, 175, 203, 0.12)`
- **Secondary:** `#c96842` (Terracotta Clay)
  - `--secondary-hover`: `#b85a35`
  - `--secondary-light`: `#da7b56`
  - `--secondary-subtle`: `rgba(201, 104, 66, 0.14)`
- **Tertiary:** `#d29a32` (Mustard Crop Gold)
  - `--tertiary-hover`: `#be8928`
  - `--tertiary-light`: `#e0ac48`
  - `--tertiary-subtle`: `rgba(210, 154, 50, 0.14)`
- **Neutral:** `#193640` (Slate Pond Depth)
  - `--neutral-dark`: `#0f232b`
  - `--neutral-light`: `#254f5d`

### Semantic Alert Colors
- **Success:** `#2ea043` (`--success-bg`: `rgba(46, 160, 67, 0.15)`)
- **Warning:** `#e3b341` (`--warning-bg`: `rgba(227, 179, 65, 0.15)`)
- **Danger:** `#f85149` (`--danger-bg`: `rgba(248, 81, 73, 0.15)`)
- **Info:** `#388bfd` (`--info-bg`: `rgba(56, 139, 253, 0.15)`)

### Surface & Background Tokens (High-Contrast Field Legibility)
- `--bg-app`: `#0c1a1f`
- `--bg-canvas`: `#0f2229`
- `--bg-surface`: `#152d36`
- `--bg-surface-elevated`: `#1a3843`
- `--bg-surface-overlay`: `rgba(21, 45, 54, 0.85)`
- `--bg-card`: `rgba(26, 56, 67, 0.65)`
- `--bg-card-hover`: `rgba(33, 68, 81, 0.85)`

### Borders
- `--border-subtle`: `rgba(54, 175, 203, 0.16)`
- `--border-medium`: `rgba(54, 175, 203, 0.32)`
- `--border-strong`: `rgba(54, 175, 203, 0.55)`
- `--border-light`: `rgba(255, 255, 255, 0.08)`

---

## 2. Typography Hierarchy

### Font Families
- **Headlines:** `Fraunces`, Georgia, serif (Warm, organic, agrarian authority)
- **Body & Controls:** `Inter`, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif (High-legibility Grotesque)
- **Data, Rates & Hashes:** `IBM Plex Mono`, 'Courier New', monospace (Tabular figures for financial calculations and HMAC proofs)

### Type Scale
| Token | Font Family | Size | Weight | Line Height | Tracking |
|---|---|:---:|:---:|:---:|:---:|
| `headline-lg` | Fraunces | 28px | 600 | 36px | -0.3px |
| `headline-lg-mobile` | Fraunces | 24px | 600 | 32px | -0.2px |
| `headline-md` | Fraunces | 20px | 600 | 28px | normal |
| `headline-sm` | Fraunces | 18px | 500 | 24px | normal |
| `display-data` | IBM Plex Mono | 32px | 600 | 40px | -0.5px |
| `data-lg` | IBM Plex Mono | 22px | 600 | 28px | normal |
| `data-md` | IBM Plex Mono | 16px | 500 | 24px | normal |
| `data-sm` | IBM Plex Mono | 14px | 500 | 20px | normal |
| `data-xs` | IBM Plex Mono | 12px | 500 | 16px | normal |
| `body-lg` | Inter | 16px | 400 | 24px | normal |
| `body-md` | Inter | 14px | 400 | 20px | normal |
| `label-lg` | Inter | 16px | 600 | 24px | normal |
| `label-md` | Inter | 14px | 500 | 20px | normal |
| `caption` | Inter | 12px | 400 | 16px | normal |

---

## 3. Spatial System, Radii & Elevations

### Spacing Scale
- `--space-2xs`: `2px`
- `--space-xs`: `4px`
- `--space-sm`: `8px`
- `--space-md`: `12px`
- `--space-lg`: `16px`
- `--space-xl`: `24px`
- `--space-2xl`: `32px`
- `--space-3xl`: `40px`
- `--gutter`: `12px`
- `--margin`: `16px`

### Border Radii
- `--radius-xs`: `4px`
- `--radius-sm`: `8px`
- `--radius-md`: `12px`
- `--radius-lg`: `18px`
- `--radius-xl`: `24px`
- `--radius-pill`: `9999px`

### Shadows & Elevation
- `--shadow-sm`: `0 2px 6px rgba(0, 0, 0, 0.25)`
- `--shadow-md`: `0 4px 14px rgba(0, 0, 0, 0.35)`
- `--shadow-lg`: `0 10px 30px rgba(0, 0, 0, 0.5)`
- `--shadow-glow`: `0 0 25px rgba(54, 175, 203, 0.25)`
- `--shadow-inner`: `inset 0 1px 2px rgba(255, 255, 255, 0.08)`

### Transitions
- `--transition-fast`: `150ms cubic-bezier(0.4, 0, 0.2, 1)`
- `--transition-normal`: `250ms cubic-bezier(0.4, 0, 0.2, 1)`
- `--transition-smooth`: `350ms cubic-bezier(0.16, 1, 0.3, 1)`

---

## 4. Stitch Cataloged Screen Domains (Project 6127167441810181608)

The Stitch project catalogs 149 screens across 8 major domains:
1. **Auth Flows (5 screens):** Splash branding, language selection, mobile +91 OTP authentication, DPDP consent, role selection.
2. **Farmer Dashboard & Marketplace (11 screens):** Agri-weather advisory, live mandi rates ticker, APMC net realization comparison, listed lot summaries.
3. **Buyer Discovery & Negotiation (22 screens):** Lot search, commodity filtering, bilateral chat offer ladder, counter-offer submission, cryptographic contract generation.
4. **Transport & Logistics (8 screens):** ONDC logistics quotes, carrier comparison, cold-chain selection, dispatch confirmation, shipment tracking.
5. **Storage & Post-Harvest (9 screens):** WDRA accredited warehouse search, cold storage arbitrage calculator, eNWR receipt reservation.
6. **Ratings & Reviews (8 screens):** Counterparty reputation, delivery quality score, dispute feedback.
7. **FPO Operations & Aggregation (23 screens):** Multi-farmer batch pooling, grade distribution, bulk warehouse deposit, auction listing.
8. **Admin Verification & Audit (12 screens):** Assay model version verification, DPDP consent revocation audit, KYC checks, dispute settlement.


---

# Stitch Exported Design System: Rural Commerce Material Baseline

## Design System Tokens (YAML)

\\yaml

\
---

## Brand & Style

This design system establishes a rural-first, high-trust agricultural commerce experience optimized for mobile Android hardware across regional India. Operating on a strict Material 3 foundation, it prioritizes radical economic clarity, transparency, and transactional certainty over decorative software trends. 

### Core Aesthetic Pillars
- **Anti-Speculative Clarity:** Avoids artificial gamification, synthetic badges ("Top Seller", "Trusted Seller"), and opaque AI confidence scores. Value is conveyed through factual breakdowns (`Gross − Deductions = Net Realization`) with strict visual provenance tags (Actual, Forecast, Estimate, Recommendation).
- **Physical Groundedness:** Utilitarian and tactile without decorative noise. The interface avoids glassmorphism, heavy drop shadows, neon accents, and futuristic glows. Contrast relies on crisp surfaces, 1dp structural hairlines, and distinct surface fills.
- **Strict Color Philosophy:** Absolutely zero green is permitted across the brand identity, navigation, and transactional states. This eliminates agricultural software clichés while ensuring high visual distinctiveness through an earth-and-sky balance: atmospheric Sky Blue and interactive Clear Blue countered by earthen Burnt Orange and Market Amber.
- **Multilingual Resilience:** Built around Indian linguistic realities across six scripts (Latin, Devanagari, Kannada, Telugu, Tamil). Layouts are fluid and text containers expand up to 200% system font scales without clipping or truncation.

## Layout & Spacing

The layout is engineered around a baseline Android mobile target of **360dp × 640dp**, preserving layout integrity down to **320dp** viewports without horizontal scrolling or clipping.

### Layout Philosophy
- **Rhythm & Grid:** Built on an uncompromising **4dp atomic grid system**. Screen margins use `16dp`, section margins use `24dp`, and horizontal card grids separate elements with a `12dp` gutter.
- **Responsive Envelopes:** On larger displays (foldables and tablets), content width is capped at `600dp` centered horizontally in a single dominant column to prevent scanning fatigue and maintain thumb accessibility.
- **Dynamic Content Growth:** Text containers must accommodate at least `150%` horizontal expansion to allow seamless script switching from English to regional Indic equivalents. Containers never declare fixed heights around text layers.
- **Touch Targets:** All interactive controls maintain a strict minimum bounding box of `48dp × 48dp`, separated by at least `8dp` of clear margin.

## Elevation & Depth

This design system enforces a **0dp elevation standard** across all layers. Traditional blurred drop shadows, ambient spreads, and Material surface tints are prohibited. 

Visual hierarchy is constructed purely through structured flat surfaces and structural linework:
- **Surface Contrast:** Background screens reside on `Canvas (#F4FAFC)`, while content modules, sheets, and cards sit on crisp `Surface (#FFFFFF)`. Secondary callouts and recessed blocks leverage `BlueMist (#E2F3F8)` or `Sand (#FFF3DF)`.
- **Structural Outlines:** Surfaces are bounded by a consistent `1dp` solid hairline border using `Line (#D7E7EB)`.
- **Focused & Active Depth:** Interactive elements receive a `2dp` stroke in `ClearBlue (#147F9E)` when focused or selected.
- **Modals & Overlays:** Dialogs and bottom sheets use a flat `#FFFFFF` surface bounded by a `1dp` border, suspended over a solid `Ink @ 40%` (`rgba(25, 54, 64, 0.40)`) backdrop scrim.

## Components

### Buttons
- **Primary CTA (`ClearBlue` Fill):** Height minimum `56dp`, width 100% in task flows. `10dp` radius. Text uses `label-lg` in `#FFFFFF`. Single dominant action per screen rule.
- **Secondary / Outlined Button:** Height `56dp`, `10dp` radius, `1dp` border in `Slate (#607780)` or `ClearBlue (#147F9E)`, background transparent. Label in `ClearBlue`.
- **Key Action / Opportunity Button:** Solid `BurntOrange (#C96842)` fill with `#FFFFFF` text. Reserved for decisive conversion actions (e.g., "Accept Offer", "Lock Price").

### Input Fields
- Minimum height `56dp`, `10dp` border radius. Fill uses `#FFFFFF` over `#F4FAFC` canvas.
- Hairline `1dp` border in `Slate (#607780)` at rest; switches to `2dp` `ClearBlue (#147F9E)` upon focus.
- Validation errors display a `1dp` border in `Danger (#C64F48)` accompanied by an icon and helper text below the field.

### Provenance & Status Badges
Badges are non-interactive structural indicators with `6dp` radius, `data-xs` or `label-md` type, and strict text-icon pairing:
- **Actual (Verified Factual Data):** `BlueMist (#E2F3F8)` container, `ClearBlue (#147F9E)` text and check icon.
- **Forecast (Predicted Trend):** `Sand (#FFF3DF)` container, `MarketAmber (#D29A32)` text and trend icon. 1dp dashed `MarketAmber` border.
- **Estimate (Calculated Approximation):** `Sand (#FFF3DF)` container with `BurntOrange (#C96842)` text and calculator icon. Value prefixed with `≈`.
- **Recommendation:** `BlueSoft (#C7E8F0)` container with `Ink (#193640)` text and a solid 4dp leading vertical edge.

### Cards
- Standard cards use `Surface (#FFFFFF)` fill, `12dp` radius, and `1dp` border in `Line (#D7E7EB)`. Internal padding is `16dp`.
- Cards never show shadows.
- Recommendation cards incorporate a `4dp` solid `ClearBlue (#147F9E)` leading bar on the left edge.

### Checkboxes & Radio Controls
- Minimum touch bounding box of `48dp × 48dp`. Checkbox corner radius is `4dp`.
- Selected state uses a solid `ClearBlue (#147F9E)` fill with a white check glyph. Unselected state uses a `2dp` stroke in `Slate (#607780)`.
