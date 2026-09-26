# MittiMandi — Android UI/UX Design Source of Truth

**Tagline:** "Know the Market. Choose Better. Sell Smarter."

| | |
|---|---|
| **Document** | `design.md` — UI/UX foundation for the native Android app |
| **Version / status** | 0.1 — Foundation draft for review |
| **Date** | 20 September 2026 |
| **Platform** | Native Android only (Kotlin · Jetpack Compose · Material 3) |
| **Not covered** | PRD, architecture, backend design, code, test plans, marketing |
| **Audience** | Product owner, designers, Android engineers, AI coding agents |

> There is **no `prd.md`** at the time of writing. This document derives requirements from the project brief and prior project context (§2) and is complete enough for a PRD to be written from it. It does not reference or fabricate a PRD.

---

## 0. How to read this document

### 0.1 Provenance tags

Every requirement or decision carries a tag so that confirmed facts are never confused with assumptions.

| Tag | Meaning |
|---|---|
| **[C]** | **Confirmed** — stated explicitly in the current project brief. |
| **[P]** | **Carried** — taken from earlier MittiMandi project context (the SIH PS 26132 SRS work and the earlier web prototype specification). Treated as intended behaviour but should be re-confirmed for Android. |
| **[A]** | **Assumption** — a design decision made here to fill a gap. Can be changed without contradicting any confirmed requirement. |
| **[D]** | **Design decision** — a deliberate resolution of an ambiguity or contradiction in the brief (see Appendix A). |
| **[Q#]** | **Requires clarification** — behaviour genuinely cannot be determined. The document states a safe default and the impact of getting it wrong. Full list in §2.5. |

### 0.2 Normative language

**MUST / MUST NOT** = mandatory. **SHOULD** = default unless a documented reason exists. **MAY** = optional.

### 0.3 Conventions used throughout

- "Seller" = a Farmer **or** an FPO acting on a lot. "Buyer" = a Buyer account. [A]
- Money is written `₹1,16,000` (Indian digit grouping). Price is `₹29/kg`. Quantity is `4,000 kg`. [C]
- Illustrative numbers in this document (e.g. 4,000 kg × ₹29/kg) are **examples only**, not data.
- Screen IDs: `AUTH-`, `FRM-`, `BYR-`, `FPO-`, `TRN-`, `STG-`, `ADM-`, `SHR-` (shared across roles).

---

## 1. Product foundation

### 1.1 Identity [C]

**MittiMandi** is a farmer-first agricultural **market-intelligence and transaction** platform delivered as a native Android app.

### 1.2 The problem and the question the UI must answer [C]

Farmers cannot easily determine where to sell, to whom, at what price, at what quality, with what transport cost, whether storage helps, and what they will *actually receive*.

The whole UI is organised around one question:

> **"If I sell this crop today, where should I sell it, to whom, at what price, and after transport, storage and other legitimate costs, how much will I actually receive?"**

### 1.3 Core product journey [C]

The information architecture, navigation and screen order follow this chain. Each step maps to specific screens.

| # | Journey step | Primary screens | Data character |
|---|---|---|---|
| 1 | Farmer | FRM-01 Dashboard, FRM-02 Profile | Actual |
| 2 | Crop / Produce | FRM-04 My Crops, FRM-05 Add Produce, FRM-06 Produce Details | Actual (user-entered) |
| 3 | Market | FRM-07 Market Dashboard, FRM-08 Current Prices | Actual (source + time) |
| 4 | Price | FRM-08, FRM-10 Price Forecast | Actual / Forecast |
| 5 | Demand | FRM-07, FRM-11 Market Opportunity, FRM-12 Buyer Discovery | Actual / Estimate |
| 6 | Buyer | FRM-12, FRM-13 Buyer Profile, FRM-14 Buyer Requirements | Actual |
| 7 | Quality | FRM-14 (buyer's quality requirement), FRM-05 (produce photos) | Actual |
| 8 | Negotiation | SHR-03 Offers, SHR-04 Negotiation | Actual |
| 9 | Agreement | SHR-05 Agreement | Actual (locked) |
| 10 | Logistics | FRM-16 Logistics, SHR-08 Delivery Tracking | Estimate → Actual |
| 11 | Storage | FRM-17 Storage, FRM-18 Storage Analysis | Estimate / Forecast |
| 12 | Order | SHR-06 Order Details | Actual |
| 13 | Delivery | SHR-08 Delivery Tracking | Actual (last known) |
| 14 | Payment | SHR-09 Payment | Actual |
| 15 | Transaction record | SHR-10 Digital Receipt, SHR-11 Transaction History | Actual |

### 1.4 Design principles

These resolve conflicts between competing design choices. When two principles collide, the lower number wins.

1. **Money first, in the farmer's units.** Price is always `₹/kg`, quantity always `kg`. No quintal or tonne on any card, list, form or calculation. The single exception is the read-only *source-unit disclosure* inside the data-source sheet (§4.7). [C][D]
2. **Show what I will receive.** Net realization is shown wherever a price is shown as a decision input. A headline price alone is never the decision number. [C]
3. **Truthful labels.** Every number is visibly one of *Actual*, *Forecast*, *Estimate* or *Recommendation*, with source and time. Forecasts are never presented as promises. [C]
4. **Never stale-as-fresh.** Cached data always shows when it was last synced. [C]
5. **One primary action per screen.** A farmer on a small phone in sunlight must see the next step immediately. (One documented exception: the neutral Sell-now vs storage decision, FRM-18, shows two equal-weight actions so that neither is implied as advice.)
6. **Plain words, any language, any text size.** Nothing is fixed-width; nothing depends on English string length. [C]
7. **Irreversible means confirmed.** Locked values are visibly locked and cannot be edited; critical actions are explicitly confirmed. [C]
8. **Security is calm.** Face verification looks like an identity check, not an entertainment feature. [C]
9. **No invented trust.** No ratings, scores, badges or metrics unless the data source defines them; otherwise "Information not available". [C]
10. **Calm and agricultural.** Warm paper surfaces, flat cards, thin borders. Motion appears only when analysis is genuinely happening. [C]

### 1.5 Usage context (constraints, not personas)

Only conditions stated in the brief are designed for. No personas or demographics are invented.

- Small Android phones; large touch targets; dynamic font scaling. [C]
- Rural, unreliable connectivity; stale data must be obvious. [C]
- Eleven languages with text expansion. [C]
- Users range from farmers to businesses to operators; the **Farmer** experience takes priority for simplicity. [C]

---

## 2. Requirements baseline

### 2.1 Requirement register (derived from the brief)

Stable IDs allow a future PRD and test plan to trace back to this document.

| ID | Requirement | Tag | Designed in |
|---|---|---|---|
| PLAT-01 | Native Android; Kotlin, Compose, Material 3, Navigation Compose, ViewModel, StateFlow, Coroutines, Room, WorkManager, DataStore, Repository pattern, REST/JSON | C | §3 |
| PLAT-02 | Android mobile only (no web/desktop/cross-platform design) | C | §3 |
| ROLE-01 | Five public roles: Farmer, Buyer, FPO, Transport Provider, Storage Provider | C | §10, §12 |
| ROLE-02 | Admin is a protected operational role; never a public registration option | C | §9.4, §12.7 |
| AUTH-01 | Mobile number + OTP/security verification | C | AUTH-03/04 |
| AUTH-02 | Language selection (11 languages) | C | AUTH-02, §7 |
| ONB-F | Farmer onboarding: mobile, OTP, name, basic details, face, state/district/taluk/village, land (acres), crops, FPO | C | AUTH-06 |
| ONB-B | Buyer onboarding; buyer does **not** select crops produced; states requirements instead | C | AUTH-07, BYR-02 |
| ONB-O | FPO, Transport, Storage onboarding incl. face capture | C | AUTH-08..10 |
| PRD-01 | Produce: crop, quantity (kg), actual harvest date, open to negotiation Yes/No | C | FRM-05 |
| PRD-02 | Two mandatory photos (single sample, full lot); optional video | C | FRM-05, ProducePhotoCard |
| FMT-01 | Price `₹/kg` primary; quantity `kg` | C | §4.7 |
| MKT-01 | Market: current, nearby, comparison, min, max, modal, arrivals, history, trend, tomorrow + 7-day forecast, confidence, up/down indicator, multi-market comparison, price alerts, opportunity alerts | C | FRM-07..11 |
| MKT-02 | Actual / Forecast / Estimate / Recommendation visually distinguishable | C | §5 |
| NET-01 | Net realization = Gross − Transport − Storage − Other legitimate agreed costs | C | NetRealizationCard |
| BUY-01 | Buyer discovery: profile, verification, location, crop, quantity, quality, offer, multi-buyer comparison, negotiation, history, reliability info, demand alerts, open-to-negotiation | C | FRM-12..14 |
| BUY-02 | Never invent ratings or trust scores; else "Information not available" | C | §5.5 |
| NEG-01 | Both parties set Open to Negotiation; Offer → Counter → Agreement | C | SHR-04 |
| NEG-02 | On agreement price, quantity and amount lock; amount auto-calculated, not editable | C | SHR-05 |
| NEG-03 | Farmer contact number revealed only after both agree, per transaction rules | C / Q2 | SHR-05 |
| TXN-01 | Transaction shows Order ID, crop, qty, ₹/kg, gross, transport, storage, net, payment method/status, delivery status, timestamp, audit info | C | SHR-06 |
| PAY-01 | Bank transfer and UPI/online; states Pending/Processing/Successful/Failed; no provider claims | C | SHR-09 |
| DEL-01 | Tracking: transporter, vehicle, location, route, ETA, distance remaining, status, last updated; last-known on failure; no "perfect real-time" claim | C | SHR-08 |
| STO-01 | Sell-now vs consider-storage comparison; forecasts labelled | C | FRM-18 |
| WEA-01 | Current weather, extreme alerts, notifications, crop-specific risk, weather-based recommendation updates; no custom weather AI | C | FRM-15 |
| OFF-01 | Offline-capable: profile, market info, draft produce/lot, saved buyer/transport/storage info. Online-only: fresh prices, new offers, negotiation sync, payments, live tracking, face verification, fresh weather | C | §6 |
| OFF-02 | Visible: Offline, Last synced, Pending synchronization, Sync failed | C | §6 |
| LNG-01 | English, Hindi, Marathi, Kannada, Telugu, Tamil, Gujarati, Punjabi, Bengali, Malayalam, Odia; text expansion; no fixed-width English-only buttons | C | §7 |
| FAC-01 | Face states: permission, camera, position guidance, capture, processing, success, failure, retry | C | §9.2 |
| RPT-01 | Simple REPORT; automatic evidence; statuses Reported / Suspicious Activity / Under Investigation / Resolved; never auto "Fraud Confirmed" | C / Q7 | §9.3 |
| VIS-01 | Exact palette; no additional primary brand colour | C | §4.1 |
| VIS-02 | Fraunces / Inter / IBM Plex Mono | C | §4.2 |
| VIS-03 | Calm, flat, thin-bordered; no glassmorphism, neon, futuristic gradients, heavy shadows | C | §4 |
| VIS-04 | Scan line only during meaningful analysis | C | §4.8 |
| CMP-01 | Reusable component set | C | §11 |
| SCR-01 | Screen groups for all six roles | C | §12 |
| STA-01 | Ten states per major screen | C | §13 |
| ACC-01 | 48dp targets, contrast, screen readers, font scaling, colour-independent status, simple language, small screens, text expansion | C | §8 |
| SCOPE-01 | No invented features (AI, ratings, providers, trust scores, guaranteed forecasts, voice, crop recommendations, blockchain, social, gamification) | C | Appendix A |

### 2.2 Screens added because a confirmed requirement has no surface

The brief lists screen groups but omits surfaces that its own requirements need. These are **added**, each tied to a confirmed requirement:

| Added screen | Why it is needed |
|---|---|
| **FRM-15 Weather** | WEA-01 defines a weather module, but no Weather screen is listed in the Farmer group. |
| **FRM-19 Price & Demand Alerts** | MKT-01 requires price alerts and market-opportunity alerts; users need a place to create/manage them. |
| **SHR-12 Sync Status** | OFF-02 requires Pending synchronization and Sync failed; users need to see and retry items. |
| **SHR-13 Sell Offer composer (Send Offer)** | NEG-01 begins with an Offer; the brief does not list the screen that creates one. |

### 2.3 Prior project context carried forward [P]

Used only where the brief is silent. Each item is flagged for re-confirmation.

| Item | Detail |
|---|---|
| Transaction lifecycle | Offer → Negotiation → Agreement → Price Lock → Quantity Lock → Face Verification → Order Created → Transport → Delivery → Payment → Receipt → Completed |
| Actions requiring face verification | Farmer: confirm sale. Buyer: confirm purchase, confirm receipt. Transport: confirm pickup, confirm delivery. Storage: confirm booking → **Q3** |
| Delivery stages | Accepted → Navigate to Pickup → Reached Pickup → Produce Loaded → In Transit → Reached Buyer → Delivered |
| Tracking privacy | Location visible only to farmer/seller, buyer, transporter and authorised admin, and only for an active order |
| Buyer expected price | A range (min–max ₹/kg); a single value is a range with min = max |
| Quality vocabulary | "Grade A", "Grade B", "Any" |
| Payment sequence | Buyer pays after confirming receipt → **Q10** |
| Forecast disclaimer | "Price forecasts are estimates and are not guaranteed future prices." |
| Admin alert tabs | New / Under Investigation / Resolved / History |
| Grievance statuses | Submitted → Under Review → Action Required → Resolved |
| Crop set (9) | Onion, Tomato, Potato, Wheat, Rice, Maize, Soybean, Cotton, Sugarcane → **Q14** |
| Report evidence | Offer, negotiation, order, payment, verification, transport, storage, delivery status, timestamps, audit log |
| Offline extras | Cached transaction history is readable offline |

### 2.4 Assumptions [A]

| ID | Assumption |
|---|---|
| A1 | One mobile number = one role account (multi-role → Q5). |
| A2 | Mobile numbers are Indian (`+91`, 10 digits starting 6–9). |
| A3 | OTP is 6 digits; resend cooldown 30 s. SMS auto-fill uses a permission-free mechanism. |
| A4 | Farmer "nearby markets" are computed from the registered location, **not** device GPS, so farmers never need location permission. |
| A5 | Bottom navigation holds ≤ 5 destinations; secondary destinations live in a navigation drawer. |
| A6 | Light theme only in v1 (dark theme → Q16). |
| A7 | Negotiation is **structured price offers only**; no free-text chat. |
| A8 | The counterparty is not shown a contact number before agreement; name/business, district and village are visible. |
| A9 | Numerals are Western Arabic (0–9) in all languages (→ Q17). |
| A10 | Any participant in a transaction (farmer, buyer, FPO, transporter, storage provider on that order) may use REPORT. |
| A11 | Transporter location is shared only while a delivery is active, with a visible indicator. |
| A12 | The break-even price in Storage Analysis is derived arithmetic on the same inputs, not new data; removable without affecting any requirement. |
| A13 | Notification permission is requested in context (not at first launch). |
| A14 | Session expiry preserves local drafts and returns the user to the screen after re-verification. |

### 2.5 Requires-clarification register

Each entry shows the **default this document uses** so design can proceed, and what changes if the answer differs.

| ID | Question | Default used | Impact if different |
|---|---|---|---|
| Q1 | The brief names an "NCP/NPC server" but does not define it. What is it (protocol, auth, offline sync contract)? | UI depends only on repository interfaces; backend-agnostic. | Sync, auth and error-mapping specs in §6/§9 may need adjusting. |
| Q2 | Contact reveal: who sees whose number after agreement (buyer↔farmer, transporter, storage)? Full number or call-only? | Farmer's number shown to buyer at agreement. Buyer→farmer and transporter visibility: shown only if backend payload says so. "Call" opens dialer. | ContactRevealCard content and SHR-05. |
| Q3 | Which actions require face verification during transactions? | The [P] list in §2.3. | Number of FaceVerification touchpoints. |
| Q4 | Can face capture/verification be deferred when offline? | No: capture/verification require internet; nothing is queued. | Offline onboarding and transaction flows. |
| Q5 | Can one person hold multiple roles under one mobile number? | No (A1). | Adds a role switcher after login. |
| Q6 | How does Admin sign in, and is Admin in the same app package? | Same login, role assigned server-side; no public Admin option, no Admin hint in UI. | Entry flow and packaging. |
| Q7 | Report outcomes: when may "Fraud Confirmed" appear, and what are the Resolved outcomes? | UI never shows "Fraud Confirmed" unless the backend returns an explicit admin-confirmed outcome; wording then supplied by backend. | ADM-08 and SHR-06 report block. |
| Q8 | What "reliability information" exists for buyers? | Only factual fields returned by backend, each labelled; otherwise "Information not available". | BuyerCard content. |
| Q9 | Forecast confidence: how is it defined and who supplies it? Range or point forecasts? | Categorical Low/Medium/High plus a reason, supplied by backend; ranges only. Never a percentage. | Forecast components. |
| Q10 | Payment: who pays whom and when; is bank transfer initiated in-app or recorded by reference; how do transport/storage get paid? | Buyer pays after receipt confirmation; UI is provider-agnostic; bank transfer shown as one method whose flow the backend defines. | SHR-09, TRN/STG payments. |
| Q11 | What are "other legitimate agreed costs"? Who agrees them? | Shown only as backend-supplied line items; users cannot type arbitrary costs. | NetRealizationCard input model. |
| Q12 | Who books transport: seller only, or buyer too? | Seller books. | FRM-16 ownership. |
| Q13 | FPO ↔ farmer linking: invite, request, or FPO-created? Can FPO sell on members' behalf? How are proceeds shared? | Farmer chooses an FPO in onboarding; membership shows "Pending FPO confirmation". Proceeds sharing is **not designed**. | FPO-02/03/04. |
| Q14 | Full crop list, local-language names, image assets (photo vs illustration, licensing)? | Nine crops [P]; bundled WebP images. | CropImageCard assets. |
| Q15 | Notification delivery (push provider, high-priority delivery-request alerts, sound)? | In-app notification centre always; OS delivery mechanism undefined. | Alert timing while app closed. |
| Q16 | Minimum Android version, device baseline, APK size budget, dark theme? | Not constrained; light theme. | Fonts, image assets, theming. |
| Q17 | Numerals: native digits per language or Western digits? | Western digits (A9). | Number formatter. |
| Q18 | Weather provider, alert definitions, and the rule source for "crop-specific risk" and "recommendation updates"? | Content is backend-supplied and labelled with source; UI never generates advice. | WeatherCard, FRM-09. |
| Q19 | Map/navigation provider and update frequency; in-app turn-by-turn or hand-off to another navigation app? | Map is an abstraction (MapPanel); navigation hands off to an external app via intent. | TRN-06, SHR-08. |
| Q20 | Offer expiry, negotiation round limits, withdrawal, partial-quantity agreement? | None defined; UI shows no expiry. Offer quantity ≤ available lot quantity. | SHR-04 rules. |
| Q21 | Can unverified buyers/FPOs/providers transact before admin verification? | They see "Verification pending" and can browse; transacting is blocked. | Onboarding completion states. |
| Q22 | Grievance categories, help content, SLAs? | Category list from backend; no SLA text. | SHR-14. |
| Q23 | Legal consent and retention wording for face images and location? | Rationale screens shown; legal text supplied by owner. | AUTH camera rationale. |
| Q24 | Produce verification: what is checked when the scan line runs at lot creation? | Completeness/upload check only (both photos present, uploaded). No quality grading claimed. | FRM-05 scan-line use. |
| Q25 | Video limits (duration/size), gallery upload vs camera-only for photos, audio permission? | Camera-first; gallery permitted via system photo picker; video optional and size-capped by backend rule. | PhotoUploadCard. |
| Q26 | "Basic details" and "Verification information" field lists for each role? | Minimum fields only (name, business name, etc.); further fields server-driven. | Onboarding forms. |
| Q27 | What "risk" means in Storage Analysis beyond forecast uncertainty? | Shows forecast range width, forecast confidence, storage duration and suitability only. No spoilage claims. | FRM-18. |
| Q28 | Splash/tagline localisation; logo asset status? | Tagline shown in English only; logo asset outside this document. | AUTH-01. |
| Q29 | Storage cost: is the time basis "per kg per day", and are there minimum/maximum durations? | Per kg per day [P]; durations shown only if the provider defines them. | STG-02, FRM-17/18 cost display. |
| Q30 | Face verification: attempt limit, and what alternative exists for a user who cannot complete it (disability, damaged/absent front camera)? | No attempt limit shown; no alternative path designed; failure keeps the action pending and points to Help. | SHR-07, accessibility of critical actions. |
| Q31 | Can the capture library detect a face and give live position guidance ("Move closer")? | Static instructions are the minimum; live guidance shown only if the library supports it. | SHR-07 guidance state. |
| Q32 | Buyer "demand" indicator: how is it defined, who supplies it, and is it Actual or Estimate? | Shown as supplied by the backend with the data type it declares. | OpportunityCard, MarketCard, FRM-07. |
| Q33 | Bulk lots: harvest-date rule when members harvested on different dates, and member attribution/consent. | Not designed beyond total kg per member; single harvest date not enforced. | FPO-04. |
| Q34 | May a transporter's stage updates be recorded offline and synced later with device timestamps? | No: stage updates need internet. | TRN-06, SHR-08. |
| Q35 | Digital receipt: may it be shared/exported, and in what format? | View-only in the app. | SHR-10. |

---

## 3. Platform and UI architecture constraints [C]

This section defines only what the **UI design** requires of the Android stack. It is not an architecture document.

### 3.1 Stack and its UI consequence

| Technology [C] | UI/UX consequence |
|---|---|
| Kotlin + Jetpack Compose + Material 3 | Every screen and component is a composable. Material 3 is the base; MittiMandi tokens (§4) **override** M3 defaults for colour, shape, elevation and type. |
| Navigation Compose | One nav graph per role plus an auth graph (§10). Deep links from notifications land inside the correct role graph with a synthetic back stack. |
| ViewModel + StateFlow + Coroutines | Each screen exposes one immutable `UiState` stream. Composables are stateless and receive state + event lambdas. |
| Room | Source of the "Last synced" experience: all lists render from local storage first, then refresh. Drafts and pending uploads live here. |
| WorkManager | Sync, photo/video upload and retry run outside the screen lifecycle. The UI shows their state (§6) but never depends on the screen being open. |
| DataStore | Language, data-saver preference, notification preferences, onboarding progress, and last-selected produce. |
| Repository + REST/JSON | UI depends on repository interfaces only. The backend server ("NCP/NPC", **Q1**) is not assumed by any screen. |

### 3.2 Screen anatomy (applies to every screen)

```
Route (nav destination)
 └─ Screen composable          stateless; renders UiState; emits UiEvent
     ├─ TopBar                  title, back/menu, contextual actions
     ├─ ConnectivityBanner      OfflineBanner slot (§6)
     ├─ Content                 one LazyColumn; sections of cards
     └─ StickyActionBar         the single primary CTA (when applicable)
```

- **One primary CTA per screen** (exception: FRM-18, §12.2), placed in the sticky bottom bar for flows and forms, or as the first card action on dashboards. [D]
- No floating action buttons (they add elevation and cover content on small screens). [D]
- Screens do not perform business calculations. Net realization, totals and break-even values arrive from a domain formatter that is unit-tested; the UI only displays.

### 3.3 Standard screen state model

Every screen state is the combination of **one content state** and **independent overlays**. This is the model behind §13.

| Content state | Meaning |
|---|---|
| `Loading` | First load with no cached data. |
| `Content(data, freshness)` | Data available; `freshness` ∈ Fresh / Stale / Unknown. |
| `Empty(reason)` | Loaded successfully but nothing to show; the reason drives the message. |
| `Error(kind, retryable)` | Could not load; `kind` ∈ Network, Timeout, Server, NotFound, Validation, Conflict, Unknown. |

| Overlay (independent) | Values |
|---|---|
| Connectivity | Online · Slow · Offline |
| Sync | Synced · Pending(n) · Syncing · Failed(n) |
| Session | Active · Expired |
| Authorization | Allowed · Unauthorized |
| Permission | Granted · Denied · Permanently denied (only for screens that need one) |

**Rule:** overlays never replace content that is available offline. Offline + cached data = `Content(Stale)` with a banner, not an error screen.

### 3.4 Data contract the UI requires [A]

To make §5 enforceable, every value that the UI shows as a market/decision figure MUST carry these fields (from repository/domain):

`value` · `unit` · `type` (Actual / Forecast / Estimate / Recommendation) · `asOf` (timestamp) · `sourceLabel` · optionally `targetDate` (forecasts) and `basis` (estimates/recommendations).

The UI MUST NOT render an Actual, Forecast or Estimate without `asOf` and `sourceLabel`. If missing, it renders "Information not available".

### 3.5 Devices and layout envelope

| Item | Rule |
|---|---|
| Reference size | 360 × 640 dp portrait. Must remain fully usable at **320 dp** width. |
| Text scale | Fully functional at **200 %** system font scale. No fixed-height text containers; use minimum heights only. |
| Orientation | Portrait is primary. Landscape must not break layouts (scrollable, no clipping) but is not optimised. Camera capture screens may lock portrait. |
| Larger screens | Single column, content capped at 600 dp width and centred. No tablet/desktop layouts are designed (Android mobile only). [C] |
| Insets | Edge-to-edge; status/navigation bar and IME insets respected; sticky bars sit above the IME. |
| Keyboard | Numeric keypad for quantity, price, land area, OTP. Decimal allowed for ₹/kg and acres; digits only for kg and OTP. |

### 3.6 Strings and text handling

- All copy comes from string resources (`UiText`); **no concatenated sentences**; use placeholders and plurals.
- Numbers and currency are formatted by one shared formatter (§4.7), never inline.
- Layouts are designed against strings **50 % longer than English**, and validated with pseudo-localisation (§7.4).

---

## 4. Design foundations

### 4.1 Colour [C]

The palette below is exact. **No other brand or accent hue may be introduced.** Tints are derived by blending a palette colour over Paper and are not new brand colours.

#### 4.1.1 Base palette

| Token (Compose) | Name | Hex | Primary role |
|---|---|---|---|
| `MossGreen` | Primary Moss Green | `#2F4A34` | Primary buttons, headings, active navigation, focused input outline |
| `MossLight` | Secondary Moss Light | `#4C7A56` | Links, secondary actions, positive/progress icons, focus ring |
| `Clay` | Clay / Earth | `#A9622E` | Agricultural accent: icons, strokes, dashed forecast border, large emphasis. Sparingly. |
| `Wheat` | Wheat / Gold | `#D8A94A` | Opportunity and analysis highlights, scan line, forecast/attention containers (as tint) |
| `Paper` | Paper | `#FAFAF7` | Screen background **and** card surface |
| `PaperDeep` | Paper Deep | `#F2F0E8` | Recessed surfaces: input fill, skeletons, stale-data panels, estimate containers |
| `Ink` | Ink | `#23271F` | Primary text |
| `Muted` | Muted | `#6B6F62` | Secondary text, input outlines, inactive icons |
| `Border` | Border | `#E1DDD0` | Card borders, dividers |
| `Danger` | Danger | `#B33A3A` | Errors, destructive actions, warnings only |

Pure white and pure black are **not used**. Cards use `Paper` with a 1 dp `Border` stroke on a `Paper` screen, so cards are defined by their border, not by colour difference. [D]

#### 4.1.2 Derived tints (blend over Paper — not new colours)

| Token | Hex | Recipe | Used for |
|---|---|---|---|
| `MossTint` | `#E2E8E0` | MossLight 14 % over Paper | Selected nav indicator, selected chip, positive badge background |
| `WheatTint` | `#F3E8D1` | Wheat 22 % over Paper | Forecast container, attention badge background, opportunity highlight |
| `ClayTint` | `#EFE5DB` | Clay 14 % over Paper | Estimate-related accent background |
| `DangerTint` | `#F1E3E0` | Danger 12 % over Paper | Error/critical badge and banner background |
| `Scrim` | Ink @ 40 % | — | Dialog and sheet scrim |

#### 4.1.3 Contrast facts (WCAG 2.x relative luminance; **verify in tooling before release**)

| Pair | Ratio | Rule |
|---|---|---|
| Ink on Paper / Paper Deep | ≈ 14.5 : 1 / ≈ 13.3 : 1 | All body text. |
| Muted on Paper | ≈ 4.9 : 1 | Secondary text ≥ 14 sp. Meets AA. |
| Muted on Paper Deep | ≈ 4.5 : 1 | Borderline. Use only for non-critical captions; critical text uses Ink. |
| Paper on Moss Green | ≈ 9.3 : 1 | Primary button label. |
| Moss Green on Paper | ≈ 9.3 : 1 | Headings, active items. |
| Moss Light on Paper | ≈ 4.7 : 1 | Links (**always underlined** — not colour alone). |
| Paper on Danger / Danger on Paper | ≈ 5.6 : 1 | Destructive button label; error text. |
| Ink on Wheat | ≈ 7.0 : 1 | Text on solid Wheat is Ink. |
| Clay on Paper | ≈ 4.5 : 1 | **Treat as failing for small text.** Clay is never used for body text or as a button fill; icons/strokes/large (≥ 18 sp) text only. |
| Wheat on Paper | ≈ 2.1 : 1 | **Never text, never a meaningful boundary.** Decorative or paired with icon + text. |
| Paper on Wheat | ≈ 2.1 : 1 | **Never** light text on Wheat. |
| Border on Paper | ≈ 1.3 : 1 | Decorative card borders and dividers only. **Never** the only boundary of an input. |
| Input outline (Muted) on Paper | ≈ 4.9 : 1 | Meets the 3 : 1 non-text requirement. |

#### 4.1.4 Material 3 `ColorScheme` mapping

| M3 role | Value |
|---|---|
| `primary` / `onPrimary` | MossGreen / Paper |
| `primaryContainer` / `onPrimaryContainer` | MossTint / MossGreen |
| `secondary` / `onSecondary` | MossLight / Paper |
| `secondaryContainer` / `onSecondaryContainer` | MossTint / MossGreen |
| `tertiary` / `onTertiary` | Clay / Paper (large or icon use only) |
| `tertiaryContainer` / `onTertiaryContainer` | ClayTint / Ink |
| `error` / `onError` | Danger / Paper |
| `errorContainer` / `onErrorContainer` | DangerTint / Danger |
| `background`, `surface` / `onBackground`, `onSurface` | Paper / Ink |
| `surfaceVariant` / `onSurfaceVariant` | PaperDeep / Muted |
| `outline` / `outlineVariant` | Muted / Border |
| `inverseSurface` / `inverseOnSurface` | Ink / Paper (snackbars) |
| `surfaceTint` | Transparent (**disable tonal elevation**) |
| `scrim` | Ink @ 40 % |

#### 4.1.5 Colour usage rules

- **Moss Green** = the *one* primary action per area, headings, active navigation.
- **Moss Light** = links, secondary actions, positive/progress icons.
- **Wheat** = opportunity and analysis only (highlight containers, scan line). It never marks an ordinary button.
- **Clay** = agricultural identity accents (icons, dashed forecast border, price-down indicator). Sparingly.
- **Danger** = errors, destructive actions and genuine warnings **only**. A *price decrease* is not an error and is never red. [D]
- **Meaning is never colour-only.** Every colour-coded state also carries an icon and a text label (§8).
- Do not use gradients, except the single scan-line gradient (§4.8).

### 4.2 Typography [C]

| Purpose | Family | Weights |
|---|---|---|
| Headings, screen titles, card titles ≥ 18 sp | **Fraunces** | 500–600 |
| Body, labels, buttons, captions | **Inter** | 400–600 |
| Data: `₹/kg`, quantities, percentages, IDs, timestamps | **IBM Plex Mono** | 500 |

#### 4.2.1 Script coverage — a required decision [D]

Fraunces, Inter and IBM Plex Mono are **Latin-script fonts**. None cover the scripts of Hindi/Marathi (Devanagari), Kannada, Telugu, Tamil, Gujarati, Punjabi (Gurmukhi), Bengali, Malayalam or Odia. Therefore:

- The brand fonts apply to **Latin text and Latin digits**.
- For each Indic script, text falls back to an open-licence **Noto Sans** family for that script (body **and** headings; a serif Indic heading face is not assumed).
- The fallback MUST be declared in the Compose `FontFamily` chain so mixed strings (e.g. a Marathi sentence containing `₹29/kg`) render each run in the correct font.
- **Verification item:** confirm the rupee sign (U+20B9) exists in every bundled font. Where it does not, only that glyph falls back to a font that has it.
- Bundling all scripts affects APK size → **Q16**. Crop names, language names and system labels must render correctly on the Language screen (AUTH-02) before any download occurs, so those scripts' fonts must be available offline (bundled or system).

#### 4.2.2 Type scale

| Style | Font | Size / line | Weight | Use |
|---|---|---|---|---|
| Display Data | Plex Mono | 32 / 40 sp | 500 | Estimated Net Realization, hero price |
| Headline | Fraunces | 24 / 32 sp | 600 | Screen title |
| Title | Fraunces | 18 / 26 sp | 500 | Card and section titles |
| Data L | Plex Mono | 24 / 32 sp | 500 | Card-level price/amount |
| Data M | Plex Mono | 16 / 24 sp | 500 | Inline price, quantity, amount |
| Data S | Plex Mono | 14 / 20 sp | 500 | Table cells, IDs |
| Data XS | Plex Mono | 12 / 16 sp | 500 | Timestamps, "Updated 10:30 AM" |
| Body L | Inter | 16 / 24 sp | 400 | Default body |
| Body M | Inter | 14 / 20 sp | 400 | Secondary body |
| Label L | Inter | 16 / 24 sp | 600 | Buttons |
| Label M | Inter | 14 / 20 sp | 500–600 | Chips, badges, tab labels |
| Caption | Inter | 12 / 16 sp | 400–500 | Source lines, helper text. **Minimum size in the app is 12 sp.** |

#### 4.2.3 Typography rules

- Plex Mono is used **selectively**, only for the data kinds listed above. Never for paragraphs or labels.
- **No ALL-CAPS labels.** Indic scripts have no case, and uppercase transforms harm reading. Sentence case only. [D]
- **No negative letter-spacing** and no artificial letter-spacing on Indic scripts.
- **Indic profile:** line height = **1.5 ×** font size (minimum), because Indic glyphs carry tall vowel marks. Latin uses the scale above.
- Use tabular (fixed-width) figures for money so columns align; right-align numeric columns.
- Text must wrap; truncation with ellipsis is allowed **only** for non-essential secondary text (e.g. a long village name in a list row) and never for prices, quantities, statuses, buttons or dialog text.
- Headings must use the semantic `heading()` accessibility role (§8).

### 4.3 Spacing and layout

| Token | Value | Use |
|---|---|---|
| `space-1` … `space-12` | 4, 8, 12, 16, 20, 24, 32, 40, 48 dp (4 dp base) | All margins/padding |
| Screen margin | 16 dp | Horizontal padding |
| Card padding | 16 dp | Inside cards |
| Card gap | 12 dp | Between cards |
| Section gap | 24 dp | Between sections |
| Min touch target | **48 × 48 dp** | Everything tappable |
| Gap between adjacent targets | ≥ 8 dp | Prevent mis-taps |
| Primary button height | 56 dp min | Full width in flows |
| Text field height | 56 dp min | |
| List row | 56 dp min (72 dp with two lines) | |
| Bottom navigation bar | 80 dp (M3), labels may wrap to 2 lines | |
| Top app bar | 64 dp; title may wrap to 2 lines at large text | |

### 4.4 Shape, elevation, borders

| Element | Rule |
|---|---|
| Card | Radius **12 dp**, 1 dp `Border` stroke, fill `Paper`, **elevation 0** |
| Button / text field | Radius **10 dp** |
| Chip / badge | Radius **6 dp** (deliberately *not* fully round — no pills) |
| Bottom sheet / dialog | 12 dp radius, 1 dp `Border`; separated from content by `Scrim`, not by shadow |
| Image | 12 dp radius (crop/produce images) |
| Avatar | Circle, 40 dp (profile photo only) |
| Elevation | 0 dp everywhere. Tonal elevation disabled. No drop shadows. Menus use a 1 dp `Border`. |
| Dividers | 1 dp `Border` |
| Focus ring | 2 dp `MossLight`, 2 dp offset |

### 4.5 Iconography and imagery

- **Icons:** Material Symbols, *Outlined*, 24 dp, weight 400. The selected bottom-nav item uses the *filled* variant plus the `MossTint` indicator (shape, not just colour).
- Icons **never appear alone** for status, navigation or critical actions — always with a text label (or an explicit content description where a label would be redundant).
- **Crop images** [C]: recognisable, 1:1, bundled **inside the app** (WebP) so crop selection works offline and on slow networks. Asset style and licensing → **Q14**.
- **Produce photos:** 4:3, `Paper Deep` placeholder while loading, tap to enlarge (pinch-zoom). In data-saver mode, thumbnails load on tap (§6.5).
- No decorative illustrations, mascots, stock photography of people, or futuristic/“AI” imagery.

### 4.6 Motion

| Rule | Detail |
|---|---|
| Purpose | Motion only communicates state change or genuine processing. |
| Durations | 150–250 ms; standard easing; forward navigation uses a simple fade/shared-axis transition. |
| Forbidden | Parallax, bounce/spring overshoot, confetti, looping decorative animation. |
| Reduce motion | If system animation scale is 0 / “Remove animations”, all non-essential motion is replaced by an instant change; the scan line becomes a static line (§4.8). |
| Progress | Use M3 linear progress in `MossLight` plus a text label ("Loading market prices…"). Skeletons are static `Paper Deep` blocks (no shimmer). |

### 4.7 Data formatting rules [C][D]

One shared formatter implements all rules below. Screens never format numbers themselves.

| Data | Format | Notes |
|---|---|---|
| **Price** | `₹29/kg` | **Primary unit everywhere.** Up to 2 decimals, trailing zeros dropped (`₹29/kg`, `₹29.5/kg`, `₹3.4/kg`). Plex Mono. **Never** ₹/quintal as a primary value. |
| Price range | `₹30–₹32/kg` | Symbol repeated, en dash. Required for forecasts. |
| Amount | `₹1,16,000` | **Indian digit grouping** (lakh/crore), whole rupees. |
| Negative amount | `−₹500` | True minus sign (U+2212). |
| Quantity | `4,000 kg` | **kg only**, Indian grouping. No tonnes or quintals on cards, lists, forms or calculations (only the source-unit disclosure below). |
| Market arrivals | `12,40,000 kg` | Same rule. Market-level totals are also kg; if a data source publishes tonnes/quintals, the **data layer converts**. [D] |
| Estimate prefix | `≈ ₹1,06,000` | `≈` marks an Estimate. |
| Percentage | `+4.2 %`, `−1.1 %` | 1 decimal, explicit sign, Plex Mono. |
| Distance | `18 km` | |
| Duration/ETA | `42 min`, `1 h 10 min` | Estimates carry `≈`. |
| Land area | `6.5 acres` | [C] acres |
| Storage cost | `₹0.80/kg/day` | Time basis (per day) is [P] → **Q29**. |
| Date | `18 Sep 2026` | Locale month names. Farmer-entered harvest date uses the actual date. |
| Time | `10:30 AM` | Device locale/12-hour convention; IST default. |
| Order/Report/Txn ID | `MM-ON-000124` | Plex Mono, never wrapped mid-token (use non-breaking hyphens). |
| Mobile | `+91 98765 43210` | Masked as `+91 98765 XXXXX` where privacy rules require. |

**Spoken forms (TalkBack):** every money/unit value exposes a spoken `contentDescription` from a string resource, e.g. "29 rupees per kilogram", "1 lakh 16 thousand rupees", "4,000 kilograms" (§8).

**Source-unit disclosure:** if a source publishes ₹/quintal, the original unit may appear **only** inside the "Data source" details sheet as "Source unit: ₹/quintal (converted to ₹/kg)". It never appears on cards.

### 4.8 Signature scan line [C]

A thin horizontal line: gradient **transparent → `#D8A94A` → transparent**.

| Property | Value |
|---|---|
| Height | 2 dp, full width of the analysis container |
| Motion | Sweeps top → bottom of the container, ease-in-out, ~1.8 s per pass, loops while analysis runs |
| Timeout | If analysis exceeds ~8 s, stop the animation and show the timeout/error state (never spin indefinitely) |
| Reduce motion | Static line at the top edge with the text label "Analysing…" |
| Text label | Always accompanied by a text status ("Comparing markets…") announced to screen readers |

**Allowed only in these five places (and nowhere else):**

| # | Use | Screen(s) |
|---|---|---|
| 1 | Market analysis | FRM-07, FRM-11 |
| 2 | Price comparison | FRM-09 |
| 3 | Buyer matching | FRM-12 |
| 4 | Produce verification (completeness/upload check, **Q24**) | FRM-05 |
| 5 | Security verification (face capture processing) | SHR-07, AUTH face steps |

It MUST NOT appear on generic loading states, buttons, headers, cards, backgrounds, splash or empty states.

---

## 5. Data provenance and trust language

### 5.1 The four data types [C]

Anything numeric that supports a decision is exactly one of these. They differ by **container, shape, icon and wording** — not by colour alone.

| Type | Meaning | Container / treatment | Label chip (icon + text) | Value style |
|---|---|---|---|---|
| **Actual** | Reported or entered data: market prices as published, user-entered quantities, agreed/locked values, booked costs | `Paper` card, solid 1 dp border | **Actual** — check-circle icon | Ink, Plex Mono. Caption: `Source · Updated time` |
| **Forecast** | A predicted future value | `WheatTint` fill, **dashed** 1 dp `Clay` border | **Forecast** — trend icon | Always a **range** (`₹30–₹32/kg`) with a **target date** and confidence. Inline note: "Not guaranteed." |
| **Estimate** | A calculation from inputs, some of which may be estimated | `PaperDeep` (recessed) fill, solid border | **Estimated** — calculator icon | `≈` prefix. Caption: "Based on …" |
| **Recommendation** | A suggested option produced from current data | `Paper` card with a **4 dp `MossGreen` leading bar** | **Recommendation** — lightbulb icon | Never a bare verdict. Always followed by basis line and an expandable "Why this option?" |

- A **legend** ("What do these labels mean?") is one tap away from every screen that shows them (bottom sheet, plain language).
- Each chip has a screen-reader description: e.g. "Forecast. Not guaranteed."
- **Transition rule:** an Estimate becomes Actual when the underlying cost is confirmed (transport when the booking is accepted; storage when confirmed; net realization when payment succeeds). The UI re-labels it and shows the timestamp of change. [A]

### 5.2 Freshness and staleness [C]

Cached data MUST never look current.

| Freshness | Trigger | Treatment |
|---|---|---|
| **Fresh** | Loaded successfully within the data type's freshness window (**Q1/Q9** — windows undefined) | Caption: `Updated 10:30 AM` |
| **Stale** | Offline, refresh failed, or older than the window | Panel switches to `PaperDeep`; clock icon; caption `Last synced: 10:30 AM (2 h ago)`; text "May be outdated". Numbers stay visible. |
| **Unknown** | No `asOf` available | Show "Information not available" instead of the number. |

Specific rules:

- **Forecasts show their target date**, not "tomorrow": `Forecast for 21 Sep`. When a forecast's target date has passed, it is hidden behind "Show expired forecasts" and never shown as current.
- A **net realization computed from Stale inputs is itself Stale**, and says which input time it uses ("Based on prices from 10:30 AM").
- **Never show a net figure with a silently missing deduction.** If a cost is unavailable, the row shows "Not available" and the total is replaced with "Cannot calculate — transport cost not available". [D]
- **Negative net** (costs exceed sale value) is shown with a true minus sign, `DangerTint` background, and the text "Costs are higher than the sale value".
- Data-freshness windows per data type are **not defined** by the brief → the UI supports thresholds as configuration (**Q9**).

### 5.3 Status catalogue

A `StatusBadge` = **icon + text + tint**. Tone names map to §4.1.2. Text colour is always `Ink`, `MossGreen` or `Danger` (never `MossLight` or `Clay` on their own tints).

| Domain | Status → tone |
|---|---|
| **Lot** | Draft (neutral) · Pending upload (attention) · Open (positive) · In negotiation (progress) · Sold (neutral, check) |
| **Verification** | Not verified (neutral) · Verification pending (attention) · Verified (positive) · Rejected (critical) |
| **Offer** | Awaiting your response (attention) · Awaiting buyer/seller (progress) · Countered (progress) · Agreed (positive) · Rejected (neutral) |
| **Order** | Order created · Transport requested · Accepted · In delivery · Delivered · Receipt confirmed · Completed |
| **Delivery** | Accepted · Navigating to pickup · Reached pickup · Produce loaded · In transit · Reached buyer · Delivered |
| **Payment** [C] | **Pending** (attention) · **Processing** (progress) · **Successful** (positive) · **Failed** (critical) |
| **Booking (storage/transport)** | Requested (attention) · Confirmed (positive) · Declined (neutral) · Completed (neutral) |
| **Sync** [C] | Synced (positive) · **Pending synchronization** (attention) · Syncing (progress) · **Sync failed** (critical) |
| **Report** [C] | **Reported** (neutral) · **Suspicious Activity** (attention) · **Under Investigation** (progress) · **Resolved** (positive) |
| **Grievance** [P] | Submitted (neutral) · Under Review (progress) · Action Required (attention) · Resolved (positive) |

Icon vocabulary (fixed): check-circle = success/complete · hourglass = pending · sync = progress · warning-triangle = attention · error-circle = critical · lock = locked · offline-cloud = offline.

### 5.4 Mandatory wording

| Where | Required text |
|---|---|
| Any forecast surface | "Price forecasts are estimates and are not guaranteed future prices." [P] |
| Recommendation basis | "Based on current market information" [C] |
| Storage future values | Labelled "Forecast" or "Estimated"; never "will", "guaranteed", "assured" |
| Locked values | "Locked after agreement" |
| Suspicious Activity | "This transaction has been flagged for review. This is not a finding of fraud." |
| Missing data | "Information not available" |
| Tracking | "Showing last known location" + `Last updated 10:42 AM` when not fresh |

**Forbidden words** (UI copy and release notes): "guaranteed", "assured", "best market" (use "Highest estimated net"), "AI" / "smart" / "intelligent" as claims, "fraud confirmed" (unless Q7 backend outcome), "trusted seller/buyer", star ratings, "score".

### 5.5 No invented trust [C]

- **Verified badge** means only: *MittiMandi verified the submitted identity/business information*. Its help text says exactly that and does **not** imply financial reliability.
- **Reliability information** (BuyerCard) shows only **factual fields returned by the data source**, each with its definition (e.g. "Completed transactions on MittiMandi: 42"). If none: "Information not available". No stars, no scores, no percentages, no colour-graded reliability unless the backend defines a metric (**Q8**).
- **Transport and storage providers** show vehicle/capacity/availability/cost — **no ratings**.
- Nothing is labelled "Top", "Trusted", "Best" or ranked by an invented score.

---

## 6. Connectivity, offline and low-bandwidth design [C]

### 6.1 Connectivity states

| State | Meaning | UI response |
|---|---|---|
| **Online** | Requests succeed normally | No banner. |
| **Slow** | Requests time out or succeed slowly; system indicates a weak/metered connection | "Slow connection" chip; low-bandwidth behaviour (§6.5); Refresh becomes explicit. |
| **Offline** | No usable connection | Persistent `OfflineBanner`; cached content shown as **Stale**; online-only actions visibly unavailable. |

### 6.2 Capability matrix

Legend: ✅ works · ◐ works with limits · ✖ needs internet (visible reason shown).

| Capability | Offline | Notes | Tag |
|---|---|---|---|
| View own profile | ✅ | Last synced shown | C |
| View previously loaded market information | ✅ (Stale) | Every card shows `Last synced`; forecasts past target date hidden | C |
| Create **draft** produce / lot | ✅ | Saved on phone; photos stored locally; state "Pending synchronization" | C |
| View saved buyer information | ✅ (Stale) | | C |
| View saved transport information | ✅ (Stale) | | C |
| View saved storage information | ✅ (Stale) | | C |
| View cached transaction history / receipts | ✅ (read-only) | | P |
| View notifications already received | ✅ | | A |
| View cached weather | ◐ (Stale) | "Fresh weather" is online-only | A |
| Fresh market prices | ✖ | | C |
| Send/receive **new offers** | ✖ | | C |
| **Negotiation** actions and sync | ✖ | Counter/accept/reject cannot be queued | C |
| **Payments** | ✖ | Never queued; state shown as pending until confirmed | C |
| **Live tracking** | ✖ | Shows last known location + time | C |
| **Face verification** | ✖ | **Q4** | C |
| Send OTP / login / register | ✖ | | C (implied) |
| Report a transaction | ✖ | Not queued, so evidence is collected consistently. [A] | A |
| Submit grievance | ◐ | Text-only, may be queued as Pending synchronization | A |
| Create price alert | ◐ | May be queued | A |

**Rule:** anything that changes shared, time-sensitive or financial state is **online-only and never silently queued**. Only user-owned drafts and low-risk preferences are queued.

### 6.3 Required UI elements

| Element | Specification |
|---|---|
| **OfflineBanner** | Directly under the top bar, full width, `WheatTint` fill, offline-cloud icon, text **"Offline. Showing saved information."**, optional "Details" link. Persistent while offline. Announced once (polite live region) when the state changes. |
| **Last synced** | On every data screen: `Last synced 10:30 AM` (Data XS). When Stale, it becomes prominent (§5.2). |
| **Pending synchronization** | `SyncStatusChip` on each queued item and a top-bar sync icon with a count. |
| **Sync failed** | Chip turns critical (`DangerTint`, error icon, "Sync failed") with a "Retry" action; a banner on affected screens. |
| **Back online** | Snackbar: "Back online. Syncing 3 changes…" → "All changes synced" or "Sync failed. Retry." |
| **Disabled online-only actions** | Button renders in disabled style **and** helper text under it: "Needs internet". No tooltip-only explanations. |

### 6.4 Sync behaviour

- Reconnection triggers background sync (WorkManager); the user can also **pull to refresh** or tap **Sync now** in SHR-12.
- **SHR-12 Sync Status** lists each pending/failed item: type, created time, state, plain-language effect ("Your draft lot is saved on this phone. Buyers cannot see it yet."), **Retry** and (for drafts only, with confirmation) **Delete**.
- **Lot lifecycle:** Draft (on phone) → Pending upload (photos uploading) → Open. A lot is not shown to buyers until both mandatory photos have uploaded. [A]
- **Uploads:** photos/videos upload resumably in the background; per-file state Queued · Uploading n % · Uploaded · Failed (Retry).
- **Conflicts:** agreed/locked data is **server-authoritative**; offline edits never overwrite it. If a draft can no longer be submitted (e.g. lot already sold elsewhere), the item shows the reason and offers Edit or Delete. Detailed contract → **Q1**.
- Signing out while items are pending shows a warning listing the count (§9.6).

### 6.5 Low-bandwidth mode [A]

The brief requires low-bandwidth design without defining a mode. Design: **automatic** on Slow connections plus a **manual "Data saver"** switch in Settings (SHR-02). While active a small "Data saver on" chip is visible.

| Behaviour | Detail |
|---|---|
| Text first | Lists render text and numbers first; images load on tap ("Tap to load photo"). |
| Crop images | Always local (bundled), so crop selection is instant. |
| Uploads | Photos are compressed before upload; **video uploads only on unmetered connections by default** (user can override). |
| No auto-polling | Data refreshes on open, pull-to-refresh and explicit "Refresh". |
| Charts | Summary values and a data table first; chart drawn on request. |
| Map | Tracking screen leads with **text status, ETA, last updated**; map tiles load on tap. |
| Pagination | Lists load in small pages (about 10). |
| Motion | Non-essential animation disabled. |

---

## 7. Multilingual design [C]

### 7.1 Languages and scripts

| Language | Native name | Script | Fallback font family |
|---|---|---|---|
| English | English | Latin | Brand fonts |
| Hindi | हिन्दी | Devanagari | Noto Sans Devanagari |
| Marathi | मराठी | Devanagari | Noto Sans Devanagari |
| Kannada | ಕನ್ನಡ | Kannada | Noto Sans Kannada |
| Telugu | తెలుగు | Telugu | Noto Sans Telugu |
| Tamil | தமிழ் | Tamil | Noto Sans Tamil |
| Gujarati | ગુજરાતી | Gujarati | Noto Sans Gujarati |
| Punjabi | ਪੰਜਾਬੀ | Gurmukhi | Noto Sans Gurmukhi |
| Bengali | বাংলা | Bengali | Noto Sans Bengali |
| Malayalam | മലയാളം | Malayalam | Noto Sans Malayalam |
| Odia | ଓଡ଼ିଆ | Odia | Noto Sans Oriya (Odia) |

(Fallback family names are design intent; final font packaging → **Q16**.)

### 7.2 Text-expansion rules

- Design every string container for **≥ 150 % of the English length**. Translations of Tamil, Telugu, Malayalam and Kannada can be considerably longer than English.
- **No fixed-width buttons or chips.** Buttons have a minimum width, grow with content, and may wrap to two lines. Full-width buttons are preferred in flows.
- Bottom-navigation labels may wrap to two lines; labels are kept short in every language.
- Rows never rely on a single line: title + value layouts stack vertically when they do not fit (value moves below label).
- Tables become stacked "label: value" rows at large text or long strings.
- No text inside images. No abbreviations that do not translate ("Qty", "Est.") — use full words or icons with labels.
- Do not concatenate sentence fragments; each sentence is a single string resource with placeholders and plural forms.
- Hyphenation is off; line breaks follow script rules (Compose default).
- Uppercase transforms are never applied (§4.2.3).

### 7.3 Behaviour

- **First launch:** Language screen (AUTH-02). Pre-select the device language if supported; otherwise English. Each option shows the native name and the English name.
- **Change any time:** SHR-02 Settings. Applies immediately without restarting the app or losing state.
- **Persistence:** stored in DataStore and applied before the first frame after splash.
- **Missing translation:** falls back to English — never a blank, a key name, or a mixed layout error.
- **Server content** (crop names, location names, alert text, weather text) is shown in the user's language if supplied; otherwise in the original language, with no attempt to machine-translate on device.
- **User-entered text** (names, business names, notes) is shown exactly as entered.
- **Tagline:** shown in English on the splash screen only (**Q28**).

### 7.4 Localisation QA requirements

- A **pseudo-locale** with ~50 % expansion and tall diacritics must render every screen without clipping.
- Key screens (Farmer Dashboard, Market Comparison, Negotiation, Agreement, Payment, Face Verification) are reviewed in the three longest-string languages at **200 % font scale**.
- All money/quantity strings are verified to render `₹`, digits and units in the correct fonts within Indic sentences.

---

## 8. Accessibility [C]

### 8.1 Requirements

| Area | Requirement |
|---|---|
| Touch targets | Minimum **48 × 48 dp** for every tappable element, with ≥ 8 dp between targets (chips and icon buttons keep a 48 dp hit area even if the visual is smaller). |
| Contrast | Text ≥ 4.5 : 1; large text and meaningful non-text UI ≥ 3 : 1 (see §4.1.3 for forbidden pairings). |
| Screen reader (TalkBack) | Every element has a meaningful role, label and state. Cards are merged into one focus stop with a full sentence, plus custom actions for their buttons. |
| Dynamic type | Works up to **200 %**. Text never clips; containers grow. |
| Focus | Visible 2 dp `MossLight` ring; logical order = visual order; dialogs trap focus and restore it on close. |
| Colour independence | Every status/data type has icon + text + shape (§5). Links are underlined. |
| Language level | Short sentences (aim ≤ 15 words), everyday words, no jargon without a help affordance. Terms like "modal price" have an info sheet ("The most common trading price"). |
| Small screens | Verified at 320 dp width, 200 % font scale, longest translation. |
| Text expansion | §7.2. |

### 8.2 Screen-reader semantics

- **Headings:** screen titles and section titles use the heading role.
- **Money and units:** spoken forms, e.g. "29 rupees per kilogram", "4,000 kilograms", "1 lakh 16 thousand rupees" (from string resources; Western digits, Indian grouping in speech).
- **IDs:** read in groups ("M M, O N, zero zero zero one two four").
- **Data type:** every value is announced with its type: *"Estimated net realization, approximately 1 lakh 6 thousand rupees, estimated."* *"Forecast for 21 September, 30 to 32 rupees per kilogram, not guaranteed."*
- **Status changes** (offline, payment result, delivery stage, sync) use polite live regions; errors use assertive.
- **Charts** have a text summary and an equivalent data table. Maps have a text equivalent (status, ETA, distance, last updated).
- **Images:** crop images have the crop name; produce photos say "Onion sample photo" / "Onion full lot photo".
- **Locked values** are read as "Locked. Price 29 rupees per kilogram." — they are *read-only text*, not disabled inputs.

### 8.3 Forms and errors

- Labels are always visible above the field (no placeholder-only labels); helper text under the field.
- Errors: icon + text under the field **and** an error summary at the top for multi-error forms; focus moves to the first error; the error says what to do ("Enter quantity in kg").
- Numeric fields show a live formatted preview under the input ("4,000 kg") so grouping is verified without formatting while typing.
- Destructive/irreversible actions use a `ConfirmationDialog` whose confirm button names the action ("Reject offer"), not "OK".

### 8.4 Time, motion, flashing

- No action is time-limited except OTP entry; the OTP timer is announced and the resend option is explicit.
- No content flashes more than three times a second. All motion respects the system "remove animations" setting (§4.6).

---

## 9. Security and sensitive-interaction design

### 9.1 Permissions

Ask **in context**, never in a batch at first launch. Each permission follows: **Rationale → System prompt → Denied → Permanently denied**.

| Permission | When requested | Used for | If denied |
|---|---|---|---|
| **Camera** | On tapping "Capture face" or a produce photo/video button | Face capture/verification, produce photos, optional video | Explain why; offer Retry; if permanently denied show "Open Settings". For produce photos, the system photo picker is offered as an alternative (**Q25**). Face steps cannot be skipped (**Q30**). |
| **Location (foreground)** | Transporter accepts a delivery / starts navigation | Sharing position for an active delivery only (A11) | Delivery can continue; tracking shows "Location not shared" and last known location. |
| **Notifications** (Android 13+) | After the first offer/order/delivery relevant event, with a rationale | Offers, orders, delivery, payment, weather, alerts | Everything still visible in the in-app notification centre. |
| **Microphone** | Only if optional video with sound is recorded (**Q25**) | Video audio | Video can be recorded silently or skipped. |
| Photos/media | **No permission**: system photo picker | Choosing produce photos | — |
| SMS | **No permission**: OTP auto-fill via a permission-free mechanism (A3) | OTP | User types the code. |

**Farmers and buyers are never asked for location permission** (A4).

Camera rationale copy (plain, security-toned): "MittiMandi uses your camera to take a clear photo of your face so we can confirm it is you. The photo is used for identity checks." Legal/retention wording → **Q23**.

### 9.2 Face capture and verification [C]

Two modes share one screen (SHR-07) and one component (`FaceVerificationDialog`, full-screen):

| Mode | Where | Outcome |
|---|---|---|
| **Capture** | Onboarding (all five roles) | A face photo is captured and saved to the profile |
| **Verification** | Critical transaction actions (§2.3, **Q3**) | The action completes only after identity is verified |

#### 9.2.1 State model [C]

| State | What the user sees | Notes |
|---|---|---|
| **Permission** | Rationale screen → system prompt. Denied/permanent-denied variants. | §9.1 |
| **Camera** | Front-camera preview with a simple oval guide, action title ("Security check" / "Take your photo"), one instruction line. | No filters, no face mesh, no emoji. |
| **Position guidance** | One short, plain instruction at a time: "Face the camera", "Move closer", "Find more light", "Hold still". | Dynamic guidance depends on the capture library (**Q31**); static instructions are the minimum. |
| **Capture** | Large "Capture photo" button (≥ 72 dp). Capture mode: Review step with **Use this photo / Retake**. | Verification mode captures and proceeds automatically. |
| **Processing** | Frame stays; **scan line** sweeps; text "Verifying identity…"; Cancel available. | Scan line rule §4.8 (#5). |
| **Success** | Check icon + "Identity verified" (verification) / "Face photo saved" (capture). Auto-continues after ~1 s or via a Continue button. | Announced via live region. |
| **Failure** | Error icon + reason + "Try again" and "Cancel". Reason categories: *Could not read your face* · *Face did not match* · *Network problem* · *Camera problem*. | **Never** reveals scores. Attempt limits and any alternative path → **Q30**. |
| **Retry** | Returns to Camera with the failure guidance retained; previous attempt discarded. | The pending action keeps its state. |

Rules:

- The pending business action (e.g. "Confirm sale") is **not completed** on failure and **loses no data**.
- Tone is a security check, not entertainment: neutral copy, no animation beyond §4.8, no "AI"/"scan magic" wording.
- Verification requires internet (**Q4**): offline shows "Face verification needs internet." and keeps the action pending; nothing is queued.
- The captured face photo is shown only to its owner (own profile) and to authorised admin verification (ADM-03, **Q6**).

### 9.3 Report / suspicious activity [C]

**Goal:** a farmer or buyer reports a transaction in **one tap plus one confirmation**; MittiMandi **automatically collects the evidence** so the user fills no complaint form.

| Step | UI |
|---|---|
| Entry | "Report transaction" (outlined, flag icon, `Danger` text) in the overflow area of SHR-06 Order Details and SHR-11 rows. Not a primary button. |
| Confirm | `ReportDialog`: title **"Report this transaction?"**; body **"MittiMandi will automatically collect the transaction details and send them for review. You do not need to fill a form."**; buttons **Report transaction** / **Cancel**. |
| Submitting | Loading state with text "Sending report…". Requires internet (**§6.2**). |
| Success | Check icon + **"Report submitted"** + Report ID (Plex Mono) + list of what was collected (chips): *Offer history · Negotiation history · Order details · Payment status · Verification · Transport · Storage · Delivery status · Timestamps · Activity log*. |
| Afterwards | Status badge on the order: **Reported**. Tapping shows the report timeline. |

**Statuses (in order):** Reported → Suspicious Activity → Under Investigation → Resolved. [C]

| Status | User-facing meaning (copy) |
|---|---|
| Reported | "We received your report." |
| Suspicious Activity | "This transaction has been flagged for review. This is not a finding of fraud." |
| Under Investigation | "Our team is reviewing this transaction." |
| Resolved | "The review is complete." + outcome text from backend (**Q7**) |

- The words **"Fraud Confirmed"** appear **only** if the backend returns an explicit admin-confirmed outcome, in wording supplied by the backend (**Q7**). Never inferred, never automatic.
- Whether the counterparty is informed of a report is **not defined** (**Q7**); the UI does not show or promise it.
- A second report on the same transaction shows the existing report instead of creating a duplicate (unless the earlier one is Resolved).
- Report is distinct from **grievances** (SHR-14), which are free-form issues.

### 9.4 Protected Admin role [C]

- Admin **never** appears in AUTH-05 Role Selection, in registration, or in any public string, deep link or navigation label.
- Admin accounts sign in through the normal login and receive the Admin graph by server-assigned role (**Q6**).
- A non-admin reaching any Admin destination sees the generic **"This page isn't available"** screen (does not confirm the section exists).
- Every Admin write action uses a `ConfirmationDialog`; actions are audit-logged (backend requirement, [P]).
- Admin screens that show personal data mask by default and reveal on explicit tap.

### 9.5 Locked values and contact reveal [C]

**Locked state** (after agreement):

- Price (`₹/kg`), Quantity (`kg`) and Amount (`₹`) are shown as **read-only text rows** with a lock icon and the label "Locked after agreement". There are no input fields, steppers, edit icons or "Edit" menu items.
- Amount is `quantity × price` computed by the app; it is displayed as a formula: `4,000 kg × ₹29/kg = ₹1,16,000`.
- Attempting to reach an edit route (deep link or back stack) redirects to the read-only view.

**Contact number** (`ContactRevealCard`) — three states:

| State | Display |
|---|---|
| Before agreement | Lock icon + "Contact number hidden until both parties agree." |
| After agreement (visible per rule) | "Agreement confirmed" + number (Plex Mono) + "Call" (opens the dialer). |
| Not applicable | Component not rendered. |

The **farmer's number is revealed only after both parties agree** [C]. Who else sees whom is **Q2**; the card renders whatever the backend marks visible. Once revealed it cannot be un-revealed, and the reveal moment is recorded in the activity log. Because the reveal happens **at agreement** — before both parties have completed face verification — a number stays visible even if the deal is later not confirmed; a confirmation time limit is **Q20**.

### 9.6 Session, authorisation and sign-out

| Situation | UI |
|---|---|
| **Session expired** | Full-screen "Your session has expired. Verify your mobile number to continue." → OTP screen; on success the user returns to the same screen. Drafts and pending items are preserved (A14). |
| **Unauthorized** (role/permission mismatch) | "You don't have access to this section." + "Go to Home". Admin variant per §9.4. |
| **Sign out** | Confirmation dialog. If sync items are pending the dialog states the count and offers "Sync first" (default) or "Sign out anyway". |
| **Sensitive display** | Mobile numbers masked outside the agreement rule; face photos per §9.2; payment details show status, method and amount only (no card/bank numbers stored or displayed by the UI). |

---

## 10. Navigation architecture

### 10.1 Graph overview

```
App
├─ Auth graph ......... AUTH-01 → 02 → 03 → 04 | 05 → 06–10
├─ Farmer graph ....... bottom nav (5) + drawer
├─ Buyer graph ........ bottom nav (5) + drawer
├─ FPO graph .......... bottom nav (5) + drawer
├─ Transport graph .... bottom nav (5) + drawer
├─ Storage graph ...... bottom nav (5) + drawer
├─ Admin graph ........ bottom nav (4) + drawer   (server-assigned role only)
└─ Shared destinations  SHR-01…14 (reachable from role graphs; content adapts to role)
```

**Start-destination logic (splash decides):**

| Condition | Destination |
|---|---|
| No language chosen | AUTH-02 Language |
| Language set, no session | AUTH-03 Login |
| Valid session | Role home |
| Expired session | OTP re-verification (§9.6) |

### 10.2 Authentication and onboarding flow

```
Splash → Language → Login ─(mobile)→ OTP ─→ existing account → Role home
                      │
                      └─ "Create account" → Role Selection → Role registration
                                             (mobile → OTP → role steps → review) → Role home
```

- Role Selection appears **only on the Create-account path** (five public roles; no Admin). A returning user never sees it (A1, **Q5**). [D]
- Registration steps are numbered ("Step 3 of 9"), one task per step, with Back, and **progress is saved locally** so an interruption does not lose entered data.

### 10.3 Navigation structure per role

Bottom navigation has **≤ 5 destinations** (A5). Everything else is in the **navigation drawer**, opened from the top-bar menu icon. The top bar always shows: menu · title · notification bell (with count) · sync indicator.

| Role | Bottom navigation | Drawer / secondary |
|---|---|---|
| **Farmer** | **Home** (FRM-01) · **My Crops** (FRM-04) · **Market** (FRM-07) · **Buyers** (FRM-12) · **Deals** (SHR-03 hub: Offers · Orders · History) | Weather (FRM-15) · Logistics (FRM-16) · Storage (FRM-17) · Alerts (FRM-19) · Notifications (SHR-01) · Help & Grievances (SHR-14) · Settings (SHR-02) · Profile (FRM-02 → Farm Details FRM-03) · Sync status (SHR-12) |
| **Buyer** | **Home** (BYR-01) · **Requirements** (BYR-02) · **Lots** (BYR-03) · **Deals** (BYR-04 Offers · BYR-05 Negotiations · BYR-06 Orders) · **Payments** (BYR-08) | Delivery (BYR-07) · Transactions (BYR-09) · Alerts (BYR-10) · Notifications · Help · Settings · Profile (BYR-11) · Sync status |
| **FPO** | **Home** (FPO-01) · **Farmers** (FPO-02) · **Lots** (FPO-03 Produce · FPO-04 Bulk Lots) · **Market** (FPO-05 Markets · FPO-06 Buyers) · **Deals** (FPO-07 Offers · Orders · FPO-08 Logistics · FPO-10 Transactions) | Storage (FPO-09) · Notifications · Help · Settings · Profile · Sync status |
| **Transport** | **Home** (TRN-01) · **Requests** (TRN-03) · **Deliveries** (TRN-04 Bookings · TRN-05 Active) · **Vehicles** (TRN-02) · **Payments** (TRN-07) | Navigation (TRN-06, opened from an active delivery) · Notifications · Help · Settings · Profile (TRN-08) · Sync status |
| **Storage** | **Home** (STG-01) · **Storage** (STG-02 Storage · STG-03 Capacity) · **Requests** (STG-04 Requests · STG-05 Bookings) · **Active** (STG-06) · **Payments** (STG-07) | Notifications · Help · Settings · Profile (STG-08) · Sync status |
| **Admin** | **Home** (ADM-01) · **Verification** (ADM-03) · **Transactions** (ADM-05) · **Suspicious** (ADM-08) | Users (ADM-02) · Markets (ADM-04) · Payments (ADM-06) · Offers (ADM-07) · Grievances (ADM-09) · Reports (ADM-10) · Settings (ADM-11) |

Bottom-nav label rules: short, one concept; may wrap to two lines (§7.2). "Deals" is the umbrella for offers → negotiation → order → history; its translation must be reviewed for clarity in every language.

### 10.4 End-to-end transaction flow (who acts on which screen)

| # | Actor | Screen(s) | Result |
|---|---|---|---|
| 1 | Farmer | FRM-07 → FRM-08 → **FRM-09 Comparison** → FRM-11 Opportunity | Sees price + **estimated net realization** per market |
| 2 | Farmer | FRM-12 Buyer Discovery → FRM-13 Buyer Profile → FRM-14 Requirement | Understands buyer, quantity, quality, expected price |
| 3 | Farmer | FRM-05 Add Produce (if no matching lot) → **SHR-13 Send Offer** | Lot exists with mandatory photos; offer sent (online only) |
| 4 | Buyer | BYR-04 Offers → **SHR-04 Negotiation** | Accepts, counters or rejects |
| 5 | Both | SHR-04 (alternating counters) | Gated by both parties' Open-to-Negotiation |
| 6 | Both | **SHR-05 Agreement** | Price, quantity, amount **locked**; contact revealed per rule |
| 7 | Each | SHR-07 Face verification (**Q3**) | Each party confirms; order is created when both have confirmed |
| 8 | Seller | **SHR-06 Order Details** → FRM-16 Logistics | Books transport (estimate → booked cost); who may book is **Q12** |
| 9 | Transporter | TRN-03 Requests → TRN-06 Navigation | Accept → Navigate → Reached pickup → Loaded → In transit → Reached buyer → Delivered |
| 10 | Farmer & Buyer | **SHR-08 Delivery Tracking** | Last-known location, ETA, distance, last updated |
| 11 | Buyer | SHR-06 → SHR-07 (confirm receipt) → **SHR-09 Payment** | Payment Pending → Processing → Successful/Failed |
| 12 | Both | **SHR-10 Digital Receipt** → SHR-11 History | Transaction record |
| — | Any party | Report action on SHR-06 | §9.3 |
| — | Farmer ↔ Storage | FRM-17/18 → booking → STG-04 (confirm, SHR-07) | Storage booked; storage cost becomes Actual |

### 10.5 Notification → destination (deep links)

Deep links open the destination with a synthetic back stack (Role home → destination), require a valid session and the correct role, and otherwise show §9.6 states.

| Notification | Destination |
|---|---|
| New offer / counter offer | SHR-04 Negotiation |
| Agreement reached | SHR-05 Agreement |
| Order created | SHR-06 Order Details |
| **New delivery request** (transporter) | TRN-03 Requests |
| Delivery stage changed | SHR-08 Delivery Tracking |
| Payment due (buyer) | SHR-09 Payment |
| Payment received / receipt | SHR-10 Digital Receipt |
| Weather alert | FRM-15 Weather |
| Price alert / market opportunity | FRM-08 / FRM-11 |
| Demand alert | FRM-12 (pre-filtered to the crop) |
| Storage request (provider) | STG-04 Requests |
| Verification decision | Profile |
| Report status change | SHR-06 (report block) |
| Grievance update | SHR-14 |
| Sync failed | SHR-12 |

The notification-delivery mechanism when the app is closed is **Q15**; the in-app centre (SHR-01) always works.

### 10.6 Back and exit behaviour

| Situation | Behaviour |
|---|---|
| Registration step | Back = previous step; entered data kept. |
| **Add Produce** | Auto-saved as a draft; leaving never shows a "discard" dialog and never loses photos. |
| Other forms with unsaved input | "Discard changes?" `ConfirmationDialog`. |
| After **Agreement** | Back goes to Deals, **not** to the offer composer (values are locked). |
| After **Order created** | Back goes to Deals. |
| Face verification | Back/Cancel returns to the pending action, which remains unconfirmed. During Processing, Back asks "Cancel verification?". |
| **Payment processing** | Back is allowed; the payment stays "Processing" and the status updates when resolved. |
| Bottom-nav re-tap | Returns to that tab's root and scrolls to top. |
| System back gesture | Uses predictive back; never exits the app from a nested screen. |

---

## 11. Component library

### 11.1 Rules for all components

- Stateless, driven by parameters, with `modifier`, text as `UiText`, and an explicit accessibility label/state. No component formats numbers itself (§4.7).
- Every component defines Default · Pressed · Focused · Disabled · Loading (where relevant) · Error (where relevant).
- No nested cards (use dividers or recessed regions instead).
- A component exists only where it has a **distinct purpose** (§11.3 explains overlaps).
- Each component is independently previewable at 320 dp, 200 % font scale and a long-string locale.

### 11.2 Listed components [C]

#### Buttons

| Component | Spec |
|---|---|
| **MittiButton** | Filled `MossGreen`, label `Paper`, 56 dp min height, 10 dp radius, `Label L`. Variants: *Primary* (default), *Destructive* (`Danger` fill, only for genuinely destructive confirms). States: Pressed (darker overlay), Disabled (`Muted` @ 38 % + helper text stating why, e.g. "Needs internet"), Loading (spinner replaces icon, label stays, taps ignored). **One primary button per screen area.** No Wheat-filled or Clay-filled buttons. |
| **MittiOutlinedButton** | 1.5 dp `MossGreen` outline, `MossGreen` label, same size/states. For secondary actions. A *Text/link* variant uses `MossLight` with underline. |

**Button label rules:** verb-first, sentence case, specific, never "OK/Submit/Click here/Continue" unless truly generic. Standard labels: *Compare markets · View buyers · Create lot · Send offer · Counter offer · Accept offer · Confirm sale · Verify identity · Book transport · Track delivery · Pay now · View receipt · Report transaction*. Width is content-driven; two lines allowed.

#### Containers and data

| Component | Purpose and rules |
|---|---|
| **MittiCard** | The base container: `Paper`, 1 dp `Border`, 12 dp radius, 16 dp padding, no elevation. Variants: Default · Recessed (`PaperDeep`) · Highlight (`WheatTint`) · Alert (`DangerTint`). Clickable cards give a ≥ 48 dp target and a ripple. Optional title uses `Title`. |
| **PriceCard** | One price fact: market/crop name, price (`Data L`, `₹29/kg`), trend indicator (icon + sign + %), min / max / modal strip (three labelled values), `ProvenanceChip` + `Source · Updated`. Compact (list) and detail variants. Modal price has an info affordance ("The most common trading price"). |
| **MarketCard** | A market as an entity in a list (Market Dashboard): name, district, distance (km), price + trend, arrivals (kg), demand, `Updated`. Tap → market/price detail. |
| **MarketComparisonCard** | A market as a **comparison row**: price, distance, arrivals, demand, and **Estimated net realization as the largest figure**; checkbox to select for side-by-side comparison; expands to the full `NetRealizationCard`. The first item may carry the factual tag "Highest estimated net" (not "Best"). |
| **OpportunityCard** | The decision summary for one market: `Recommendation` chip, market + distance, price (Actual), **Estimated net** (`Display Data`), demand, verified-buyer count, expandable **"Why this option?"**, basis line "Based on current market information". Primary CTA "View buyers"; secondary "Compare markets". Never says "best". The **demand** value is shown with the data type the backend declares (**Q32**). |
| **NetRealizationCard** | The core differentiator — a readable ledger (see 11.4). |
| **BuyerCard** | Buyer name (business), `Verified` badge (with meaning sheet), location (district/village), crop image + name, required quantity (kg), quality, expected price range (`₹/kg`), required-by date, **Open to negotiation: Yes/No** (icon + text), reliability facts or "Information not available", optional "If sold here: ≈ range" net estimate, CTA "View buyer" / "Send offer". **No ratings or scores.** |
| **OfferCard** | An offer summary: counterparty, crop, quantity (kg), price (`₹/kg`), computed total amount, quality, required date, negotiation state, `StatusBadge` and whose turn. CTA by state: "Respond" / "View negotiation" / "View order". |
| **NegotiationCard** | The alternating price history and the response area (11.5). |
| **TransactionCard** | Order ID (mono), crop, quantity, agreed `₹/kg`, amount, order/payment/delivery `StatusBadge`s, date, and a `Reported` badge if applicable. Tap → SHR-06. |
| **WeatherCard** | Temperature (°C), condition, humidity/rain chance if supplied, extreme-alert banner (`DangerTint`, warning icon + text), **crop-specific risk chips** (crop + risk level as icon + text: Low/Moderate/High), backend-supplied "recommendation update" lines with source, and `Updated`. Never generates advice on device. |
| **LocationCard** | Structured location (State · District · Taluk · Village) or route endpoints (Pickup → Drop with distance). Not a map. Optional "Change". |
| **DeliveryTrackingCard** | Stage badge, transporter name, vehicle number (mono), ETA (`≈`), distance remaining, **Last updated**, map area (11.6), and the stage `Timeline`. Never labelled "Live". |
| **PaymentCard** | Locked payable amount as a formula, method selector (**Bank transfer** · **UPI / online payment**), status badge (Pending · Processing · Successful · Failed), and the single primary action (see SHR-09). No provider logos or claims. |

#### Status, timeline, feedback

| Component | Spec |
|---|---|
| **StatusBadge** | Icon + text + tint (§5.3). 6 dp radius, `Label M`. Never colour alone. Width grows with the label; may wrap. |
| **Timeline** | Vertical stepper. Node = *done* (check), *current* (ring + bold), *to do* (empty ring); each with label and timestamp. Collapsed view shows the current step and the next; "Show all steps" expands. Used for the 12-step transaction lifecycle, delivery stages, report and grievance statuses. |
| **OfflineBanner** | §6.3. |
| **EmptyState** | 48 dp `Muted` outlined icon + title + one plain sentence of guidance + optional single CTA. Copy per screen in §13.4. |
| **LoadingState** | Text label ("Loading market prices…") + linear progress (`MossLight`) + static `PaperDeep` skeleton blocks. **No scan line here.** |
| **ErrorState** | Icon + what happened + what to do + **Retry** + expandable "Details" (technical code for support). Variants: Network · Timeout · Server · Not found · Unauthorized · Session expired. Never blames the user; never shows raw exceptions. |

#### Dialogs and capture

| Component | Spec |
|---|---|
| **FaceVerificationDialog** | Full-screen. States and copy per §9.2. Capture and Verification modes. Scan line only in Processing. |
| **PhotoUploadCard** | One mandatory or optional slot: label, requirement text (**"Required"** / **"Optional"** — text, not just an asterisk), instruction ("Upload a clear sample photo." / "Upload a photo of the complete lot." / "Video is optional."), a small bundled hint image, preview, and states *Empty · Capturing · Captured · Queued (offline) · Uploading n % · Uploaded · Failed (Retry)*. Actions: Take photo · Choose from gallery (**Q25**) · Retake · Remove. |
| **ProducePhotoCard** | Read-only display of a lot's **sample photo**, **full lot photo** and optional video (thumbnail + play), 4:3, labelled, tap to enlarge with pinch-zoom. Used in Produce Details and buyers' Lots. |
| **ReportDialog** | §9.3 copy. Two buttons, no form fields. Success and Failure variants. |
| **ConfirmationDialog** | Title states the action; body states the consequence (especially irreversibility); buttons **[Specific verb]** / **Cancel**; destructive variant uses the `Danger` button. Required for: accept/reject offer, book transport, confirm pickup/delivery/receipt, pay, report, delete draft, decline request, sign out with pending sync, and every Admin write. |

### 11.3 Supporting primitives (each justified)

These are **not** extra features; each enforces a confirmed requirement in one place.

| Component | Why it must exist |
|---|---|
| **ProvenanceChip** | Enforces MKT-02: one implementation of Actual/Forecast/Estimated/Recommendation labels (§5.1). |
| **ScanLine** | Enforces VIS-04: a single implementation that can only be used in the five allowed contexts (§4.8). |
| **SyncStatusChip** | Enforces OFF-02: the four sync states on any item. |
| **StepProgress** | Multi-step registration needs a consistent "Step x of N" indicator with an accessible description. |
| **CropImageCard** | Crop selection "using recognisable crop images" [C]: image + name (selected state = border + check + `MossTint`, not colour only). |
| **ContactRevealCard** | Enforces NEG-03 (§9.5). |
| **LockedValueRow** | Enforces NEG-02: label + read-only value + lock icon; the only way to render locked price/quantity/amount. |
| **MittiTextField** | One text/numeric input contract: visible label, helper, error, live formatted preview (e.g. "4,000 kg"), 56 dp height, `Muted` outline (3:1), `MossGreen` 2 dp focus, `Danger` error. |

**Overlap clarification:** `PriceCard` (a price fact) · `MarketCard` (a market entity) · `MarketComparisonCard` (a market row with net realization) · `OpportunityCard` (one recommendation) are distinct and must not be merged or duplicated.

### 11.4 NetRealizationCard [C]

The ledger reads top-to-bottom like a receipt. Numbers right-aligned in Plex Mono; labels in Inter. Illustrative example only:

```
┌────────────────────────────────────────┐
│ Estimated net realization   [≈ Estimated]│
│ 4,000 kg × ₹29/kg                        │
├────────────────────────────────────────┤
│ Gross sale value             ₹1,16,000   │
│ − Transport cost             −₹8,000   ⓘ │
│ − Storage cost               −₹2,000   ⓘ │
│ − Other agreed costs             None  ⓘ │
├════════════════════════════════════════┤
│ Estimated net           ≈ ₹1,06,000      │  ← Display Data (32 sp)
│ ≈ ₹26.5/kg after costs                   │
│ Based on prices from 10:30 AM            │
└────────────────────────────────────────┘
```

Rules:

- The **subtraction** is explicit (− sign and word "cost") so the arithmetic is understandable.
- Each ⓘ opens the source of that line ("Transport: estimated from available providers" / "Booked with Suresh Logistics").
- **Type per line:** Gross = Actual price × entered quantity. Transport/Storage = *Estimated* until booked/confirmed, then *Actual*. Net = *Estimated* until payment succeeds, then *Actual*, and the card title changes to "Net realization".
- **Missing input:** line shows "Not available"; total becomes "Cannot calculate — transport cost not available" (§5.2).
- **Negative net:** minus sign + `DangerTint` + "Costs are higher than the sale value".
- Forecast-based scenarios (storage) show a **range** of net values with the `Forecast` treatment; never a single promised number.
- "Other agreed costs" lists individual backend-supplied lines (**Q11**); users cannot type free costs.
- Screen-reader: reads the equation as a sentence.

### 11.5 NegotiationCard

```
┌────────────────────────────────────────┐
│ Onion · 4,000 kg                         │
│ Open to negotiation:  You Yes · Buyer Yes│
├────────────────────────────────────────┤
│ You            ₹30/kg   ₹1,20,000  10:02 │
│ Shree Agro     ₹28/kg   ₹1,12,000  10:14 │
│ You            ₹29/kg   ₹1,16,000  10:20 │
│ ─ Waiting for Shree Agro to respond ─    │
├────────────────────────────────────────┤
│ [ Accept offer ]  [ Counter offer ]      │
│ [ Reject offer ]                         │
└────────────────────────────────────────┘
```

- Structured price entries only (no chat, A7). Each row: party (**You** / counterparty), price, computed total, time.
- A **turn banner** states clearly whose move it is ("Your turn" / "Waiting for the buyer").
- **Open-to-negotiation gating [C]:** if *either* party has chosen No, "Counter offer" is **not offered**; the card says "Counter offers are off because the buyer is not open to negotiation. You can accept or reject." Both parties' settings are always visible.
- **Counter offer** opens a sheet: price field (`₹/kg`, decimal keypad) with live total; for a farmer/FPO also the live *Estimated net realization* at that price. Quantity is shown, not editable in the counter (change of quantity → **Q20**).
- Accept / Reject use `ConfirmationDialog`.
- When both parties' prices match or one accepts, the card switches to the **agreed** state and the flow moves to SHR-05.
- Offline: all three actions show disabled with "Needs internet".

### 11.6 Map handling (DeliveryTrackingCard, TRN-06)

The map provider and update frequency are **Q19**. The UI is built around a `MapPanel` abstraction so the provider can change. The text block (stage, ETA, distance, last updated) is always present and is the source of truth for accessibility and low bandwidth. If no location is available: "Location not available yet" + last known location if any.

---

## 12. Screen specifications

### 12.0 How each screen is specified

Every screen lists: **Purpose · Role · Entry**, **Information hierarchy** (top to bottom), **Primary CTA / Secondary actions**, **Important data**, **States** (loading, empty, error, offline, permission — the screen-specific parts), and **Navigation / Accessibility**. Global state behaviour (§13) applies to every screen unless a deviation is stated. Wireframes are structural, not pixel designs, and use independent illustrative numbers.

### 12.1 Authentication and onboarding

#### AUTH-01 · Splash
- **Purpose:** initialise the app and decide the start destination (§10.1). **Role:** all. **Entry:** app launch (Android SplashScreen API).
- **Hierarchy:** logo → "MittiMandi" (Fraunces) → tagline "Know the Market. Choose Better. Sell Smarter." (English, **Q28**). No scan line, no progress animation.
- **CTA:** none (automatic). **States:** if local initialisation fails → `ErrorState` "Something went wrong starting the app." + "Try again". Works fully offline.
- **A11y:** announces the app name once.

#### AUTH-02 · Language
- **Purpose:** choose one of 11 languages (§7). **Entry:** first launch; later from Settings.
- **Hierarchy:** title (shown in the device language **and** English) → 11 rows, each with the **native name** (large) + English name (small) → sticky CTA.
- **CTA:** "Use this language". Tapping a row re-renders the screen in that language immediately (preview).
- **States:** fully static and offline-safe; native-script fonts must render here without any download (§4.2.1).
- **A11y:** radio-group semantics; each row is announced in its own language plus English; selected row = check icon + `MossTint` + border (not colour only).

#### AUTH-03 · Login
- **Purpose:** identify a returning user by mobile number. **Entry:** after language / session start.
- **Hierarchy:** title "Log in" → mobile field with fixed `+91` prefix and 10-digit input → helper "We will send a code to this number." → CTA → link "Create account".
- **CTA:** "Send OTP". **Secondary:** "Create account" → AUTH-05.
- **States:** invalid number → inline error "Enter a valid 10-digit mobile number"; **offline** → CTA disabled + "Needs internet"; too many attempts / server error → `ErrorState` inline (limits **Q1**); no account found → "No account for this number. Create an account?".
- **A11y:** numeric keypad; label always visible; error announced.

#### AUTH-04 · OTP verification (security verification)
- **Purpose:** verify the mobile number [C: "OTP/security verification"]. **Entry:** from AUTH-03 or from registration.
- **Hierarchy:** "Verify your number" → "Enter the 6-digit code sent to +91 98765 XXXXX" → code field (auto-filled where possible) → resend timer → CTA → "Change number".
- **CTA:** "Verify". **Secondary:** "Resend code" (enabled after 30 s), "Change number".
- **States:** verifying (inline loading); wrong code → "That code is not correct. Check and try again."; expired → "This code has expired. Send a new code."; offline → "Needs internet"; no additional challenge unless the backend requires one (**Q26**).
- **A11y:** the countdown is announced at 30/10/0 s, not every second; a single field (not 6 separate boxes) is used so screen-reader and paste work.
- **Outcome:** login → role home; registration → next step.

#### AUTH-05 · Role selection
- **Purpose:** choose the account type on the **Create account** path only. **Entry:** AUTH-03 → "Create account".
- **Hierarchy:** "How will you use MittiMandi?" → five role cards (icon + name + one plain sentence) → sticky CTA. **No Admin. No default selection.**

| Role | One-line description |
|---|---|
| Farmer | I grow crops and want to sell them. |
| Buyer | I want to buy crops. |
| FPO | I represent a farmer producer organisation. |
| Transport provider | I carry produce with my vehicle. |
| Storage provider | I provide storage for produce. |

- **CTA:** "Continue as {role}" (role name localised). Cards ≥ 72 dp, descriptions wrap.
- **A11y:** radio-group; selection announced.

#### Registration flows — common rules
- Step indicator `StepProgress` ("Step 3 of 9"); one task per screen; Back keeps data; progress persisted locally.
- Mobile + OTP are the first two steps of every flow (AUTH-03/04 screens are reused).
- Face capture uses SHR-07 in Capture mode. Location uses `LocationCard` pickers.
- Registration requires internet from the OTP step onwards; offline shows "Needs internet".
- Fields marked **Q26** show a server-driven form if the field list is not fixed.

#### AUTH-06 · Farmer registration (9 steps) [C]

| Step | Content | Rules |
|---|---|---|
| 1 | Mobile number | As AUTH-03 |
| 2 | OTP | As AUTH-04 |
| 3 | About you: **name** and basic details | Name required; other basic details **Q26** |
| 4 | Face photo | SHR-07 Capture; required |
| 5 | Location: **State → District → Taluk → Village** | Cascading searchable pickers; all four required; village-level choice sets "nearby markets" (A4) |
| 6 | Land area (**acres**) | Decimal, > 0; e.g. `6.5 acres` |
| 7 | **Crops you grow now** — `CropImageCard` grid | Multi-select; **Skip for now** allowed; "You can add produce later" |
| 8 | **FPO** (if applicable) | "Are you a member of an FPO?" Yes → search & select · No · Skip. Membership shows "Pending FPO confirmation" (**Q13**) |
| 9 | Review → **Create profile** | Section summaries with Edit; success "Profile created" → Farmer Home |

#### AUTH-07 · Buyer registration [C]
Steps: Mobile · OTP · **Business details** (buyer/business name, contact person, other fields **Q26**) · Face photo · Location · **Verification information** (server-driven, **Q26**) · Review & submit · *(optional)* **"What do you want to buy?"** (creates the first requirement, or Skip).
- The buyer is **never** asked which crops they grow or produce; every buyer-facing crop prompt says **"What crops do you want to buy?"**. [C]
- After submission the account shows "Verification pending" (**Q21**); requirements can be drafted but transacting is blocked until verified.

#### AUTH-08 · FPO registration
Steps: Mobile · OTP · **FPO profile** (organisation name, registration details **Q26**) · Face photo (representative) · Location · Verification information · Review. Member farmers are added later (FPO-02, **Q13**). Status "Verification pending" until admin verification (**Q21**).

#### AUTH-09 · Transport provider registration
Steps: Mobile · OTP · Profile (name, business name) · Face photo · **Vehicle information** (vehicle type, registration number, **load capacity in kg**) · Base location · Review. Availability is set later on TRN-01. Verification per **Q21**.

#### AUTH-10 · Storage provider registration
Steps: Mobile · OTP · Profile · Face photo · Storage location · **Storage details** (storage type, **total capacity kg**, **crop suitability** via `CropImageCard`, **cost per kg** with time basis **Q29**, storage duration limits if any) · Review. Available capacity starts equal to total capacity. Verification per **Q21**.

### 12.2 Farmer screens

#### FRM-01 · Farmer Dashboard
- **Purpose:** answer at a glance: *What is my produce worth today, where, and what needs my attention?* **Role:** Farmer. **Entry:** Home tab / after login.
- **Hierarchy (top → bottom), designed for a 360 dp phone:**
  1. Top bar: menu · "Good morning, {name}" · location (village, district) · bell · sync icon.
  2. `OfflineBanner` (conditional).
  3. **Weather alert strip** — one line, only when an extreme alert exists for the user's district/crops; taps to FRM-15.
  4. **Needs your action** — at most 2 items (offer awaiting response, verification pending, payment received to review), then "See all". Hidden when empty.
  5. **Your produce** selector (chip: crop + quantity, ▾) → **OpportunityCard** for the selected produce: the nearby market with the highest estimated net, price (Actual + `Updated`), **Estimated net realization**, demand, verified buyers, CTA.
  6. **Active order** — one compact `TransactionCard` (+ "n more").
  7. **My produce summary** — active lots count and quick "Add produce".
  8. Shortcuts row: Compare markets · View buyers.
- **Density budget:** ≤ 6 sections; ≤ 3 primary data points per card; the first screen of content shows header, at most one alert strip, and *either* "Needs your action" *or* the OpportunityCard fully. Everything else is one scroll away.
- **Primary CTA:** "View buyers" (on OpportunityCard). **Secondary:** "Compare markets", "Respond" (on action items).
- **Important data:** current produce; nearby market price (Actual); market comparison entry; **estimated net realization** (Estimate); buyer demand; weather alert; active order status.
- **States:** *Loading:* header + two skeleton cards. *Empty (no produce):* "Add your first produce" card + today's prices for **crops in the profile** (market prices do not need a lot); no crops either → prompts to add. *Error:* per-card `ErrorState`; the dashboard is never wholly blank when cache exists. *Offline:* banner + every card Stale with `Last synced`. *Sync:* pending chip in the top bar.
- **A11y:** reading order = visual order; each card is one focus stop with a sentence ("Onion, 4,000 kilograms. Nashik APMC, 29 rupees per kilogram, actual, updated 10:30 AM. Estimated net approximately 1 lakh 6 thousand rupees.").

```
┌────────────────────────────────────┐
│ ≡  Good morning, Ramesh   (bell)2 ⟳│
│    Pimpalgaon B., Nashik           │
├────────────────────────────────────┤
│ ⚠ Heavy rain expected tomorrow   › │
├────────────────────────────────────┤
│ Needs your action                  │
│ ┌────────────────────────────────┐ │
│ │ Offer · Shree Agro Foods       │ │
│ │ ₹29/kg · 4,000 kg              │ │
│ │ [Awaiting you]    [ Respond ]  │ │
│ └────────────────────────────────┘ │
│ Your produce:  Onion · 4,000 kg  ▾ │
│ ┌────────────────────────────────┐ │
│ │ [Recommendation]               │ │
│ │ Nashik APMC · 18 km            │ │
│ │ ₹29/kg  ↑ +4.2 %   [Actual]    │ │
│ │ Updated 10:30 AM               │ │
│ │ Estimated net   ≈ ₹1,06,000    │ │
│ │ Demand: High · 7 verified buyers│ │
│ │ [ View buyers ]  Compare markets│ │
│ └────────────────────────────────┘ │
│ Active order                       │
│ MM-ON-000124 · In transit        › │
├────────────────────────────────────┤
│ Home  Crops  Market  Buyers  Deals │
└────────────────────────────────────┘
```

#### FRM-02 · Farmer Profile
- **Purpose:** view/manage identity. **Entry:** drawer → Profile.
- **Hierarchy:** name + masked mobile → verification/face-photo status (text + icon) → location summary → FPO membership status → Farm Details link → Language → Sign out.
- **CTA:** none primary; "Edit details". **States:** editing offline saves locally and shows Pending synchronization; re-capturing the face photo needs internet. **A11y:** statuses read as sentences.

#### FRM-03 · Farm Details
- **Purpose:** location, land area (acres), crops grown, FPO. **Entry:** Profile.
- **Hierarchy:** `LocationCard` (state, district, taluk, village) → land area → crops (`CropImageCard` chips) → FPO.
- **CTA:** "Save changes". Changing the location shows "Nearby markets will update after you save." **States:** offline edit queued; validation as registration.

#### FRM-04 · My Crops
- **Purpose:** manage crops grown and produce lots. **Entry:** My Crops tab.
- **Hierarchy:** tabs **My produce** | **Crops I grow** → list of lots (crop image, quantity kg, harvest date, `StatusBadge`, `SyncStatusChip` for drafts/pending) → sticky CTA.
- **CTA:** "Add produce". **Secondary:** open a lot → FRM-06.
- **States:** *Empty:* "No produce added yet. Add your produce to compare markets and find buyers." *Offline:* drafts can be created; the list shows local items first. *Sync failed:* item chip + Retry.

#### FRM-05 · Add Produce [C]
- **Purpose:** create a sale lot. **Entry:** My Crops, Send Offer (no matching lot), Dashboard.
- **Hierarchy:** (1) Crop (`CropImageCard` grid) → (2) Quantity in **kg** (unit fixed, not selectable; live preview "4,000 kg") → (3) **Actual harvest date** (date picker; no future dates) → (4) **Open to negotiation** — explicit **Yes / No** choice with **no default** and the hint "If Yes, buyers can send counter offers." → (5) **Sample photo — Required** ("Upload a clear sample photo.") → (6) **Full lot photo — Required** ("Upload a photo of the complete lot.") → (7) **Video — Optional** ("Video is optional.").
- **CTA:** "Create lot". **Secondary:** "Save draft" (automatic autosave also runs).
- **Behaviour:** Create lot is disabled until crop, quantity, date, negotiation choice and both photos exist, and a plain list says what is missing. On press: **scan line** + "Checking your entry…" (completeness/upload check only, **Q24**), then success "Lot created" with next actions "Compare markets" / "View buyers".
- **States:** *Loading:* photo upload progress per slot. *Offline:* primary becomes **"Save draft"** with helper "Saved on this phone. It will be sent when you are online."; the lot stays *Pending synchronization* and is invisible to buyers until uploaded. *Permission:* camera rationale/denied flow (§9.1). *Error:* upload failure per slot with Retry. *Validation:* inline per field.
- **A11y:** every slot states "Required/Optional" in text; photo slots announce state ("Sample photo, required, not added").

```
┌────────────────────────────────────┐
│ ←  Add produce   Draft saved       │
├────────────────────────────────────┤
│ Crop                               │
│ [Onion ✓][Tomato][Potato][Wheat] … │
│ Quantity                           │
│ [ 4000        ] kg      = 4,000 kg │
│ Harvest date (actual)              │
│ [ 18 Sep 2026               ▾ ]    │
│ Open to negotiation                │
│ (•) Yes     ( ) No                 │
│ ┌─ Sample photo · Required ──────┐ │
│ │ Upload a clear sample photo.   │ │
│ │ [ Take photo ]                 │ │
│ └────────────────────────────────┘ │
│ ┌─ Full lot photo · Required ────┐ │
│ │ Upload a photo of the complete │ │
│ │ lot.           [ Take photo ]  │ │
│ └────────────────────────────────┘ │
│ ┌─ Video · Optional ─────────────┐ │
│ │ Video is optional. [Add video] │ │
│ └────────────────────────────────┘ │
├────────────────────────────────────┤
│ [ Create lot ]        Save draft   │
└────────────────────────────────────┘
```

#### FRM-06 · Produce Details
- **Purpose:** review one lot. **Hierarchy:** `ProducePhotoCard` (sample, lot, video) → crop, quantity (kg), harvest date, open to negotiation → status + sync state → linked offers → actions.
- **CTA:** "Compare markets" (pre-filled with this crop and quantity). **Secondary:** "View buyers", "Delete draft" (drafts only, confirmed).
- **Rules:** editing is available only while the lot has no offers or agreement (A); locked quantities are read-only (§9.5). **States:** photos load on tap in data-saver; offline shows saved photos.

#### FRM-07 · Market Dashboard
- **Purpose:** entry to price intelligence. **Entry:** Market tab.
- **Hierarchy:** crop selector chips (crops from profile/produce) → context chip "For 4,000 kg" (editable) → **highest nearby price** `PriceCard` (Actual) → nearby `MarketCard`s (top 3 + "See all") → **Forecast teaser** (tomorrow range, `Forecast` chip) → alert summary → sticky CTA.
- **CTA:** "Compare markets". **Secondary:** "Set price alert", "Price forecast".
- **States:** *Loading:* on first analysis the **scan line** runs with "Analysing nearby markets…". *Empty:* "No market data for {crop} yet." *Error/API failure:* "Unable to load live market data. Showing last synchronized information." (if cache) else `ErrorState`. *Offline:* Stale + `Last synced`.

#### FRM-08 · Current Prices
- **Purpose:** prices for one crop across nearby markets. **Hierarchy:** crop + `Source · Updated` → sort (Distance · Price) → `PriceCard` per market (price, trend, **minimum**, **maximum**, **modal**, **arrival kg**, distance).
- **CTA:** "Compare markets". **Secondary:** "Set price alert", data-source sheet.
- **A11y:** modal/min/max have info sheets in plain language.

#### FRM-09 · Market Comparison
- **Purpose:** compare markets by **what the farmer will receive**. **Entry:** Market Dashboard, Produce Details.
- **Hierarchy:** "Quantity to compare" field (kg, prefilled from the lot) → sort control (default **Estimated net realization**, visible label) → `MarketComparisonCard` list → legend link → footnote "Transport and storage costs are estimated" → sticky CTA.
- **CTA:** "Compare selected" (2–3 markets → side-by-side sheet with rows: price, distance, arrivals, demand, gross, transport, storage, other, net). **Secondary:** open a card → FRM-11.
- **States:** *Loading:* scan line "Comparing markets…". *Empty:* "No markets to compare for {crop}." *Error/offline:* stale cache with banner, or `ErrorState`. *Missing cost:* that card shows "Cannot calculate — transport cost not available" (§5.2). **No ranking label except the factual "Highest estimated net".**

#### FRM-10 · Price Forecast
- **Purpose:** show history and forecast honestly. **Hierarchy:** market/crop → segments **Tomorrow · 7 days · History** → chart (Actual = solid line; Forecast = shaded range with dashed edge, "Today" divider) → **Forecast range** with **target date** → **confidence** chip (Low/Medium/High + reason, **Q9**) → **up/down indicator** (icon + sign + %) → data table → **disclaimer strip** (always visible) → Source · Updated.
- **CTA:** "Set price alert". **States:** *No forecast:* "Forecast not available for this market." *Offline:* history cached; expired forecasts hidden; the rest Stale. *Low bandwidth:* table first, chart on request.
- **A11y:** the chart has a text summary and a table.

#### FRM-11 · Market Opportunity
- **Purpose:** the decision summary for one market. **Hierarchy:** `OpportunityCard` → **NetRealizationCard** (full ledger) → "Compared with your other options" (2 rows) → "Why this option?" (basis bullets, only those that are factually true, e.g. "Higher price than the average of other markets", "Shorter transport distance", "Lower estimated transaction cost") → basis line **"Based on current market information"**.
- **CTA:** "View buyers". **Secondary:** "Compare markets", "Set price alert".
- **States:** scan line while analysing. *Insufficient data:* "We cannot suggest an option because some market or transport information is missing." (data still shown). *Stale:* recommendation labelled with the data time. Never uses "best" or "guaranteed".

#### FRM-12 · Buyer Discovery
- **Purpose:** find whom to sell to. **Hierarchy:** crop context → **Filters** (crop, quantity, location, quality, required date, price, verified only, open to negotiation) → active-filter chips (dismissible) → demand-alert banner ("New demand for Onion") → `BuyerCard` list → "Compare selected" (up to 3 buyers).
- **CTA:** "View buyer" (card). **Secondary:** filter, sort (Required-by · Expected price · Distance), compare.
- **States:** *Loading:* scan line "Matching buyers…" (first load only). *Empty:* "No buyers match these filters." + "Clear filters". *Offline:* saved buyer information (Stale). *Error:* `ErrorState`.

#### FRM-13 · Buyer Profile
- **Purpose:** understand a buyer before offering. **Hierarchy:** business name + `Verified` badge (+ meaning) → location (district/village) → **contact: hidden** (`ContactRevealCard`) → open requirements → **transaction history** (factual counts) → **reliability facts or "Information not available"** (**Q8**).
- **CTA:** "Send offer". **Secondary:** "View requirement".

#### FRM-14 · Buyer Requirements (buyer's requirement, seen by farmer)
- **Purpose:** show exactly what the buyer wants. **Hierarchy:** crop image + name → **quantity required (kg)** → **quality** → preferred location → **required-by date** → **expected price (₹/kg range)** → **Open to negotiation** → "If you sell here: ≈ net range" (Estimate).
- **CTA:** "Send offer" (→ SHR-13). **Secondary:** "Add produce" if no matching lot.

#### FRM-15 · Weather (added, **WEA-01**)
- **Purpose:** weather that affects selling and dispatch. **Hierarchy:** current weather → **extreme weather alerts** → **crop-specific risk** for the farmer's crops (icon + text) → **recommendation updates** (backend-supplied lines with source, **Q18**) → notification link.
- **CTA:** none. **States:** *Offline:* cached weather Stale ("Fresh weather needs internet"). *No alerts:* "No weather alerts for your area." The UI never invents advice and never claims a weather model.

#### FRM-16 · Logistics
- **Purpose:** book and follow transport. **Entry:** drawer / Order Details.
- **Hierarchy:** orders grouped by transport state (**Needs transport · Requested · Accepted · In delivery**) → **provider list** when booking (name, vehicle type, capacity kg, availability, **estimated cost**, no ratings) → confirmation.
- **Booking authority:** the seller books (**Q12**).
- **CTA:** "Book transport" → `ConfirmationDialog` stating the cost and that it reduces net realization. **States:** *Empty:* "No transport providers are available right now." + "Try again later". *Offline:* saved transport info Stale; booking disabled "Needs internet". After booking the cost changes from Estimate to Actual when accepted.

#### FRM-17 · Storage
- **Purpose:** discover storage. **Hierarchy:** produce/crop + days context → provider cards (distance km, **available capacity kg**, **crop suitability**, **cost ₹/kg/day**, duration, availability) → selected provider → request.
- **CTA:** "Request storage" (needs internet). **Secondary:** "Sell now vs storage" → FRM-18. **States:** unsuitable/insufficient capacity providers are shown but marked with a text reason and cannot be requested.

#### FRM-18 · Storage Analysis — Sell now vs consider storage [C]
- **Purpose:** compare the two paths without recommending one. **Hierarchy:** inputs (produce, provider, days) → **Sell now** card (Actual price + Estimated net) → **Consider storage** card (**Forecast** range, confidence, storage cost, extra transport, duration, **risk** = range width + confidence + suitability, **Q27**, Estimated net **range**) → **Difference vs selling now (range)** → **break-even price** (A12) → disclaimer.
- **CTA:** two **equal-weight outlined** actions — "Sell now: view buyers" and "Request storage" — to avoid implying a recommendation. [D]
- **Rules:** future values are ranges labelled Forecast/Estimated; never "will"; a possible loss is shown as plainly as a possible gain. **States:** scan line while calculating; missing inputs → "Cannot calculate — {input} not available".

```
┌────────────────────────────────────┐
│ Sell now                  [Actual] │
│ Price today               ₹29/kg   │
│ Estimated net         ≈ ₹1,08,000  │
├────────────────────────────────────┤
│ Consider storage        [Forecast] │
│ Forecast in 7 days   ₹30–₹32/kg    │
│ Confidence: Medium                 │
│ − Storage (4 days)        −₹3,200  │
│ − Extra transport         −₹1,000  │
│ Estimated net  ≈ ₹1,07,800–₹1,15,800│
├────────────────────────────────────┤
│ Difference vs selling now          │
│            −₹200 to +₹7,800        │
│ Break-even price      ≈ ₹30.05/kg  │
│ Price forecasts are estimates and  │
│ are not guaranteed future prices.  │
├────────────────────────────────────┤
│ [Sell now: view buyers][Request storage]
└────────────────────────────────────┘
```

#### FRM-19 · Price & Demand Alerts (added, **MKT-01**)
- **Purpose:** create/manage price alerts and demand alerts. **Hierarchy:** existing alerts (crop, condition such as "reaches ₹30/kg", on/off) → "Add alert" sheet → note on delivery (**Q15**).
- **CTA:** "Add alert". **States:** *Empty:* "No alerts yet. Add an alert to be told when a price or buyer demand changes." *Offline:* creation queued (Pending synchronization). Triggered alerts appear in SHR-01.

### 12.3 Buyer screens

Buyer copy rule: every crop prompt for a buyer reads **"What crops do you want to buy?"** — never "grow" or "produce". Face verification applies to *confirm purchase* and *confirm receipt* (**Q3**). An unverified buyer sees a persistent "Verification pending" banner and cannot send or accept offers (**Q21**).

#### BYR-01 · Buyer Dashboard
- **Purpose:** what needs my action and what is arriving. **Entry:** Home tab.
- **Hierarchy:** top bar → verification banner (if pending) → **Needs your action** (offers awaiting response, receipt to confirm, payment due — max 2 + "See all") → **My requirements** summary (open count) → **Active orders / deliveries** (one card + "n more") → **Lots matching my requirements** (count, factual) → alerts.
- **CTA:** "Add requirement" (if none open) otherwise the top action item's button ("Respond", "Confirm receipt", "Pay now"). **States:** *Empty:* "You have no requirements yet. Add what you want to buy so farmers can find you." *Offline:* Stale banner; actions needing internet disabled with "Needs internet".

#### BYR-02 · Buyer Requirements
- **Purpose:** state what the buyer wants to buy. **Hierarchy:** list of requirement cards (crop image, quantity kg, quality, expected price range, required-by, Open to negotiation, status **Open / Closed** [A]) → sticky CTA → create/edit form.
- **Form (title "What do you want to buy?"):** **Crop** (`CropImageCard`) → **Quantity required (kg)** → **Quality requirements** (Grade A · Grade B · Any [P]; further quality detail **Q26**) → **Preferred location** (district/village) → **Required-by date** → **Expected price** (**₹/kg**, min–max; equal values allowed) → **Open to negotiation: Yes / No** (explicit, no default).
- **CTA:** "Add requirement" / "Save requirement". **Secondary:** "Close requirement" (confirmed). **States:** validation inline; offline → saved as draft with Pending synchronization (A) and not visible to farmers until synced; editing a requirement never changes existing offers.

#### BYR-03 · Farmer/FPO Lots
- **Purpose:** discover produce to buy. **Hierarchy:** filters (crop, quantity, location, harvest date, open to negotiation) → lot cards (`ProducePhotoCard` thumbnail, crop, quantity kg, actual harvest date, seller name, district/village, Open to negotiation, "Matches your requirement" tag when factual) → lot detail (sample photo, full-lot photo, video, details).
- **CTA:** "Send offer" (buyer-initiated offer, [P]) → SHR-13. **States:** *Empty:* "No lots match your filters." *Offline:* saved lots Stale; photos on tap; sending an offer needs internet.

#### BYR-04 · Offers
List of `OfferCard`s in two tabs **Received · Sent**; awaiting-response first. *Empty:* "No offers yet. When farmers respond to your requirements, offers will appear here." CTA per card: "Respond" / "View negotiation".

#### BYR-05 · Negotiations
Active negotiations with a turn indicator ("Your turn" / "Waiting for the farmer") → SHR-04. *Empty:* "No negotiations in progress."

#### BYR-06 · Orders
`TransactionCard` list (active first). Card → SHR-06. *Empty:* "No orders yet. Orders appear after both of you confirm an agreement."

#### BYR-07 · Delivery
Active deliveries with stage, ETA, last updated → SHR-08. *Empty:* "No deliveries on the way."

#### BYR-08 · Payments
- **Purpose:** pay and follow payments. **Hierarchy:** **Payment due** cards (order, locked amount, due after receipt confirmation [P, **Q10**]) → Processing → Completed/Failed history.
- **CTA:** "Pay now" (→ SHR-09). **States:** offline → CTA disabled with "Needs internet"; failed payments show a persistent Retry.

#### BYR-09 · Transactions
SHR-11 (Transaction History) scoped to the buyer.

#### BYR-10 · Alerts
Alerts about matching lots, offers, payments due and deliveries; alert preferences link to SHR-02. *Empty:* "No alerts right now."

#### BYR-11 · Buyer Profile
Business details, verification status (+ meaning), face-photo status, location, requirements shortcut, language, sign out. Editing verification information may re-enter "Verification pending" (**Q21**).

### 12.4 FPO screens

The FPO acts as a **seller** on lots. Market, Buyer, Offers, Logistics, Storage and Transactions screens reuse the Farmer/shared screens with the FPO's aggregated quantity as context. Membership linking and proceeds sharing are **not designed** (**Q13**, **Q33**).

#### FPO-01 · FPO Dashboard
- **Hierarchy:** FPO name + verification → **Registered farmers** (count) · **Available produce** (kg) · **Active lots** (count) → **Needs your action** (offers, membership requests, transport/payment items) → **Market opportunity** for the largest aggregated crop (`OpportunityCard`) → alerts.
- **CTA:** "Create bulk lot". *Empty:* "No member farmers yet." *Offline:* Stale.

#### FPO-02 · Farmers
Member list (name, village, crops, available kg) with search; member detail is read-only. **Membership requests** (farmers who selected this FPO in onboarding) with Approve / Decline (confirmed) — flow marked **Q13**. *Empty:* "No member farmers yet."

#### FPO-03 · Produce
Aggregated produce **by crop** (total kg, expandable member breakdown). CTA "Create bulk lot" for the selected crop. All quantities in kg.

#### FPO-04 · Bulk Lots
- **List:** bulk lots with status badges. **Create flow:** choose crop → choose contributing members and **kg per member** → lot **total kg is calculated and read-only** → **Open to negotiation** (Yes/No) → **Sample photo (required)** → **Full lot photo (required)** → optional video → "Create bulk lot". The harvest-date rule for lots combining multiple harvests and member attribution are **Q33**.
- **States:** as FRM-05 (draft offline, pending upload, scan line "Checking your entry…").

#### FPO-05 Markets · FPO-06 Buyers · FPO-07 Offers · FPO-08 Logistics · FPO-09 Storage · FPO-10 Transactions
Reuse FRM-07…FRM-12, SHR-03/04, FRM-16, FRM-17/18 and SHR-11 respectively, with the header naming the FPO and the quantity context defaulting to the selected bulk lot. All rules for units, provenance and states are identical.

### 12.5 Transport provider screens

Face verification applies to **confirm pickup** and **confirm delivery** (**Q3**). Tracking exposure follows A11. Ratings are never shown.

#### TRN-01 · Transport Dashboard
- **Hierarchy:** **Availability** switch with a text state ("Available for requests" / "Not available") → **New delivery request** highlight (if any) → **Active delivery** card (stage + next action) → counts: Requests · Deliveries · Completed → Payments summary.
- **CTA:** "View request" when a new request exists, otherwise "View deliveries". **States:** *Empty:* "No requests right now. You will be alerted when a delivery request arrives." *Offline:* Stale, availability change needs internet.

#### TRN-02 · Vehicles
List of vehicles (type, registration number in mono, **load capacity kg**, availability). Add/edit form: vehicle type, registration number, capacity (kg). CTA "Add vehicle". *Empty:* "Add your vehicle to receive delivery requests."

#### TRN-03 · Requests
- **Purpose:** respond to new delivery requests. **Hierarchy:** **New delivery request** cards — crop, **quantity kg**, pickup (village, district), drop (buyer location), **distance (km)**, **offered/estimated cost (₹)**, required vehicle, order ID — with an attention treatment: `WheatTint` container, warning icon **and** the words "New delivery request".
- **CTA:** "Accept order". **Secondary:** "Decline" (confirmed). **Alerting:** while the app is open a top heads-up banner appears; when closed depends on **Q15**.
- **States:** *Offline:* requests shown as Stale; Accept disabled "Needs internet". A request accepted by someone else shows "This request is no longer available." **Who sets the cost:** **Q10**.

#### TRN-04 · Bookings
Accepted, not-yet-started bookings with pickup date/time if supplied. CTA "Start navigation" opens TRN-06.

#### TRN-05 · Deliveries
Tabs **Active · Completed**. Active card: stage `Timeline` + next-action button. Completed: history with amounts.

#### TRN-06 · Navigation
- **Purpose:** run a delivery through its stages. **Hierarchy:** current stage + destination → map (`MapPanel`, **Q19**) with route → ETA, distance → **one large stage button** → stage `Timeline` → location-sharing indicator ("Sharing location for MM-ON-000124").
- **Stage buttons (in order):** "Start navigation" → "Reached pickup" → "Confirm produce loaded" (**face verification**) → "Start transit" → "Reached buyer" → "Confirm delivery" (**face verification**). Each is a `ConfirmationDialog` when irreversible.
- **States:** *Permission:* location rationale/denied (§9.1) — delivery can continue, tracking shows "Location not shared". *GPS/network failure:* "GPS not available. Your last location was sent at 10:42 AM." + Retry; recovery shows "Location updates resumed". *Offline:* stage updates need internet (default) — whether they may be recorded offline and synced with device timestamps is **Q34**.
- **A11y:** the stage button is the first focus stop; map has a text equivalent.

#### TRN-07 · Payments
Earnings per delivery (amount, status **Pending · Processing · Successful · Failed**), history. Payer and timing **Q10**. *Empty:* "No payments yet."

#### TRN-08 · Transport Profile
Profile, face-photo status, vehicles summary, verification status, language, sign out.

### 12.6 Storage provider screens

Face verification applies to **confirm storage booking** (**Q3**). Cost time basis is **Q29**.

#### STG-01 · Storage Dashboard
**Available capacity** (kg of total, with a text ratio) · **Active storage** (count) · **Requests** (count, attention) · **Bookings** · **Payments** summary. CTA "View requests" when requests are pending. *Empty:* "No storage requests yet."

#### STG-02 · Storage
Facility profile: name, location, **storage type**, **crop suitability**, **cost per kg** (`₹0.80/kg/day` format), **storage duration** limits (if any). CTA "Edit storage details".

#### STG-03 · Capacity
**Total capacity (kg)** — editable. **Available capacity (kg)** — calculated (total minus confirmed bookings) and read-only [A]. Shows the current bookings that consume capacity. CTA "Save capacity". Offline edits queue with Pending synchronization.

#### STG-04 · Requests
- **Hierarchy:** request cards — farmer (name, district), crop, **quantity kg**, **days**, **computed cost** (`quantity × cost/kg/day × days`, Estimate until confirmed), capacity check.
- **CTA:** "Confirm booking" (**face verification**). **Secondary:** "Decline" (confirmed). If the request exceeds available capacity the CTA is disabled with the visible reason "Not enough available capacity." If the crop is unsuitable the request cannot be confirmed.

#### STG-05 · Bookings
All bookings with `StatusBadge` (Requested · Confirmed · Declined · Completed) and sync state.

#### STG-06 · Active Storage
Currently stored lots: crop, quantity (kg), start date, planned duration, days elapsed, accrued cost (Estimate). CTA "Mark storage completed" (confirmed). *Empty:* "Nothing is in storage right now."

#### STG-07 · Payments
Amounts receivable per booking, status (Pending · Processing · Successful · Failed), history (**Q10**).

#### STG-08 · Storage Profile
Profile, face-photo status, verification status, language, sign out.

### 12.7 Admin screens (protected role)

Admin screens follow §9.4. On a phone they are **read-first** lists with drill-down; tables become stacked cards. Anything not defined by the brief is marked **Q** and shown as read-only.

#### ADM-01 · Admin Dashboard
Summary cards: **Active users · Farmers · Buyers · FPOs · Transport providers · Storage providers · Active orders · Completed transactions · Pending verification · Suspicious alerts**. Each card opens the relevant filtered list. Shows "Data as of {time}". *States:* Stale-aware; per-card error.

#### ADM-02 · Users
Search + filters (role, verification status). Detail shows masked personal data, reveal on tap. Actions beyond verification (suspend, block) are **not defined** (**Q6**) and therefore not designed.

#### ADM-03 · Verification
Queue of accounts in **Verification pending**. Detail: submitted verification information and face photo (access rules **Q6**). **Approve** (confirmed) or **Reject** (reason required so the user can act; wording visible to the user).

#### ADM-04 · Markets
Read-only market data status: market, crop coverage, **last updated**, source. Editing market data is **not defined** (**Q1**).

#### ADM-05 · Transactions
List/detail of orders with every TXN-01 field and the activity log. Read-only.

#### ADM-06 · Payments
Payments with state filters (**Pending · Processing · Successful · Failed**). Read-only.

#### ADM-07 · Offers
Read-only monitor of offers and negotiations (parties, price history, status).

#### ADM-08 · Suspicious Activity
- **Purpose:** review user reports. **Hierarchy:** tabs **New · Under Investigation · Resolved · History** [P] → alert cards (transaction ID, parties, crop, locked amount, reason "Suspicious activity reported by user", status) → detail with evidence sections: **Overview · Negotiation · Order · Payment · Delivery · Activity log** (all auto-collected).
- **Actions and transitions** (each confirmed and audit-logged):

| From | Admin action | To |
|---|---|---|
| Reported | "Mark as suspicious activity" | Suspicious Activity |
| Reported / Suspicious Activity | "Start investigation" | Under Investigation |
| Under Investigation | "Resolve" (outcome + note required) | Resolved |

- The outcome vocabulary and any "confirmed" wording are **Q7**. The UI never adds "Fraud Confirmed" on its own.

#### ADM-09 · Grievances
List by status (**Submitted · Under Review · Action Required · Resolved**) → detail → status change with a note shown to the user.

#### ADM-10 · Reports
Content is **not defined by the brief** (**Requires clarification**). Placeholder: read-only list of operational summaries; no invented metrics.

#### ADM-11 · Admin Settings
Language, session/sign out. Further settings **Requires clarification**.

### 12.8 Shared screens (content adapts to role)

#### SHR-01 · Notifications
- **Hierarchy:** grouped **Today / Earlier** → items (icon, title, one line, time). Unread = **bold title + "New" text label + dot** (not colour alone). Tap → destination (§10.5). "Mark all as read".
- **Types:** offers, negotiation, agreement, orders, delivery, payments, weather, price alerts, market opportunity, demand alerts, report and grievance updates, sync.
- **States:** *Empty:* "No notifications yet." *Offline:* cached items readable. *Unauthorized destination:* §9.6.

#### SHR-02 · Settings
Language · **Data saver** (§6.5) · **Notification preferences** by type · Offline data (storage used; clearing cached data warns about pending items) · Permission shortcuts (opens system settings) · Help & grievances · About/version · **Sign out**. Dark theme is not offered (A6, **Q16**).

#### SHR-03 · Offers (Deals hub)
Tabs **Offers · Orders · History**. Offers tab: awaiting-response first; `OfferCard`s; filter by status. *Empty (farmer):* "No active offers. Once buyers respond to your produce lot, offers will appear here." *Empty (buyer):* see BYR-04.

#### SHR-04 · Negotiation
- **Hierarchy:** lot + requirement summary → **turn banner** → `NegotiationCard` (§11.5) → `ContactRevealCard` (hidden state) → lifecycle `Timeline` (compact).
- **CTA (your turn):** "Accept offer" (primary). **Secondary:** "Counter offer" (only if both parties are open), "Reject offer".
- **States:** *Waiting:* actions hidden, banner "Waiting for {party}"; *Rejected:* "This offer was rejected." + link to Buyers; *No longer available:* `ErrorState`; *Offline:* history readable, actions disabled with "Needs internet"; *Sync:* none — negotiation is never queued.

#### SHR-05 · Agreement [C]
- **Purpose:** show the locked deal and collect confirmation. **Hierarchy:** "Both parties agreed" (check) → **LockedValueRows**: Price `₹29/kg`, Quantity `4,000 kg`, Amount `₹1,16,000` with the formula `4,000 kg × ₹29/kg` → `ContactRevealCard` (revealed per rule) → seller: **NetRealizationCard** / buyer: total payable → lifecycle `Timeline` (current = Face verification).
- **CTA:** seller "Confirm sale"; buyer "Confirm purchase" → SHR-07. After the user's own confirmation: "Waiting for {other party} to confirm." When both have confirmed the order is created and SHR-06 opens.
- **Rules:** no edit affordance anywhere (§9.5). Time limit for the other party's confirmation is **Q20**. Back → Deals.

```
┌────────────────────────────────────┐
│ ←  Agreement                       │
├────────────────────────────────────┤
│ ✓ Both parties agreed              │
│ (lock) Locked after agreement      │
│ Price                    ₹29/kg (lock)│
│ Quantity                4,000 kg (lock)│
│ 4,000 kg × ₹29/kg                  │
│ Amount                 ₹1,16,000 (lock)│
├────────────────────────────────────┤
│ Contact                            │
│ Agreement confirmed · +91 98765 …  │
├────────────────────────────────────┤
│ Estimated net        ≈ ₹1,06,000   │
│ (NetRealizationCard – collapsed)   │
│ Next: confirm your identity → Order│
├────────────────────────────────────┤
│ [ Confirm sale ]                   │
└────────────────────────────────────┘
```

#### SHR-06 · Order Details [C]
- **Hierarchy:** Order ID (mono) + `StatusBadge`s (order, delivery, payment, report) → **NetRealizationCard** (per-line Actual/Estimate) → fields: crop, quantity kg, agreed ₹/kg, gross amount, transport, storage, **net realization**, **payment method**, **payment status**, **delivery status**, **timestamp** → lifecycle `Timeline` (12 steps, collapsed to current + next) → transport block → storage block → payment block → `ContactRevealCard` → **Activity log** (audit information as a readable list: "Offer created · 10:02", "Agreement locked · 10:20" …).
- **CTA by role/state:** Seller: "Book transport" (none booked) → "Track delivery". Buyer: "Confirm receipt" (after delivery) → "Pay now" → "View receipt". Completed: "View receipt". **Overflow:** "Report transaction" (§9.3).
- **States:** *Offline:* cached, read-only with `Last synced`; actions disabled "Needs internet". *Reported:* report block with statuses.

#### SHR-07 · Face capture / verification
See §9.2. Parameters: **mode** (Capture / Verification) and **action label** ("Confirm sale"). Full-screen; portrait.

```
┌────────────────────────────────────┐
│ ✕   Security check                 │
├────────────────────────────────────┤
│        ┌──────────────┐            │
│        │  (camera     │            │
│        │   preview)   │            │
│        │  oval guide  │            │
│        └──────────────┘            │
│   Face the camera and hold still.  │
│                                    │
│        [ Capture photo ]           │
│   Confirming: Confirm sale         │
└────────────────────────────────────┘
```

#### SHR-08 · Delivery Tracking [C]
- **Purpose:** follow an active delivery without overstating precision. **Roles:** farmer/seller, buyer (and transporter view TRN-06). **Entry:** notification, order, Deliveries list.
- **Hierarchy:** stage badge + **"ETA ≈ 42 min · 13.4 km left"** (Estimates) → **Last updated 10:42 AM** → map (`MapPanel`) → transporter name + **vehicle number** → stage `Timeline`. Never labelled "Live".
- **States:** *Fresh:* normal. *Stale/GPS or network failure:* banner **"Showing last known location"** + last updated time, ETA marked "May be outdated". *Not started:* "Delivery has not started. Tracking begins when the transporter starts the trip." *Delivered:* final status, no map updates. *Offline:* "Live tracking needs internet. Showing last known location, updated 10:42 AM." *Data saver:* text first, map on tap.
- **Privacy:** visible only to the order's parties and authorised admin, and only while the order is active (A11).

```
┌────────────────────────────────────┐
│ ←  Delivery · MM-ON-000124         │
├────────────────────────────────────┤
│ In transit                         │
│ ETA ≈ 42 min · 13.4 km left        │
│ Last updated 10:42 AM              │
│ ┌────────────────────────────────┐ │
│ │        (map area)              │ │
│ │  Showing last known location   │ │
│ └────────────────────────────────┘ │
│ Suresh Logistics · MH-15-AB-1234   │
│ ✓ Accepted  ✓ Pickup  ✓ Loaded     │
│ ● In transit ○ Reached ○ Delivered │
└────────────────────────────────────┘
```

#### SHR-09 · Payment [C]
- **Purpose:** pay the **locked** amount and show payment state. **Buyer view:** `PaymentCard` with **LockedValueRow** amount (`4,000 kg × ₹29/kg = ₹1,16,000`, not editable), method choice **Bank transfer** / **UPI / online payment**, primary "Pay now". **Seller view:** read-only status and receivable net (Estimate → Actual).
- **Payment states:**

| State | UI |
|---|---|
| **Pending** | Method choice + "Pay now". Seller: "Waiting for buyer's payment." |
| **Processing** | "Processing payment… Please do not pay again." Progress + status live region; user may leave the screen; state persists. |
| **Successful** | Check icon, "Payment successful", Transaction ID, "View receipt". |
| **Failed** | Error icon, reason (from backend), "Payment did not complete. Check your account before trying again." + "Try again" / "Choose another method". |
| **Unknown (offline/timeout)** | "Waiting for confirmation" shown as Pending; never assumed successful. |

- **Rules:** no provider names/logos or integration claims; bank-transfer details flow is **Q10**; payment is never queued offline.

#### SHR-10 · Digital Receipt
**Transaction ID · Order ID · Crop · Quantity (kg) · Price (₹/kg) · Gross amount · Charges (transport, storage, other) · Net amount** (seller) or **Amount paid** (buyer) **· Payment method · Payment status · Timestamp** · parties. Readable offline once loaded (P). CTA "Back to order". Sharing/exporting the receipt is **Q35**.

#### SHR-11 · Transaction History
Search by Order ID; filters (status, crop, date range, "Reported"); `TransactionCard`s grouped by month. *Empty:* "No transactions yet. Active and completed orders appear here." *Offline:* cached list read-only with `Last synced`.

#### SHR-12 · Sync Status
§6.4. Lists pending/failed items with plain-language effect, Retry, and (drafts only) Delete. *Empty:* "Everything is synced." with `Last synced`.

#### SHR-13 · Send Offer
- **Hierarchy:** buyer requirement summary → **lot** selector (matching crop; "Create lot" if none) → **price (₹/kg)** field with reference chips (buyer's expected range — Actual; today's market price — Actual) → **quantity (kg)**, default = min(lot, required), ≤ lot quantity (**Q20**) → live **total amount** (calculated, read-only) → seller: live **Estimated net** → both parties' **Open to negotiation** shown.
- **CTA:** "Send offer" → `ConfirmationDialog`. **States:** online only; offline shows "Needs internet". Buyer-initiated variant reads "Send offer to seller".

#### SHR-14 · Help & Grievances
Tabs **Help · My issues**. *My issues:* list with ID, subject, status `Timeline` (Submitted → Under Review → Action Required → Resolved [P]) and admin notes. **Report an issue** form: category (server list, **Q22**), description → "Send issue". Offline: text-only issues may queue (Pending synchronization). This is separate from the one-tap transaction Report (§9.3). Help content **Q22**.

---

## 13. State design [C]

Every major screen handles **all ten states**, not only the happy path. §12 lists screen-specific behaviour; this section defines the **default pattern** used unless a screen states otherwise.

### 13.1 Default pattern for the ten states

| # | State | Trigger | Default UI pattern | A11y |
|---|---|---|---|---|
| 1 | **Loading** | First load, no cached data | `LoadingState`: text label + linear progress + static skeleton. No scan line (§4.8). Cached data, when it exists, is shown immediately instead. | Progress has a text label; polite announcement "Loading …". |
| 2 | **Success** | Data loaded | Content rendered with provenance chips and `Updated` captions. After an action: snackbar/inline confirmation with the result; irreversible successes (order created, payment successful, report submitted) use a full confirmation view with the ID. | Result announced (polite). |
| 3 | **Empty** | Loaded but no items | `EmptyState`: icon + title + one guiding sentence + at most one CTA. Empty ≠ error. | Title is a heading. |
| 4 | **Error** | Request failed and nothing cached | `ErrorState`: what happened + what to do + **Retry** + "Details". If cached data exists, show it as **Stale** with a banner instead of an error page. | Announced assertively. |
| 5 | **Offline** | No connectivity | `OfflineBanner`; content is Stale; online-only actions disabled with visible "Needs internet". | Announced once on change. |
| 6 | **Sync pending** | Local changes not yet sent | `SyncStatusChip` "Pending synchronization" on each item + top-bar count; SHR-12 lists them. | Chip text is read with the item. |
| 7 | **Sync failed** | Send failed | Chip becomes "Sync failed" (icon + text) with **Retry**; banner on affected screen; effect explained in plain words. | Announced assertively once. |
| 8 | **Permission denied** | User refused a permission | Rationale → denied screen with alternative where one exists → "Open Settings" if permanently denied (§9.1). | Focus moves to the explanation. |
| 9 | **Unauthorized** | Role/permission mismatch or removed access | "You don't have access to this section." + "Go to Home"; Admin variant "This page isn't available." (§9.4). | Heading + single action. |
| 10 | **Session expired** | Token no longer valid | Full-screen "Your session has expired. Verify your mobile number to continue." → OTP → return to the same screen; drafts preserved (A14). | Focus on the message. |

### 13.2 State coverage by screen group

Legend: **D** = default pattern; text = specific behaviour.

| Screens | Loading | Empty | Error | Offline | Sync pending / failed | Permission | Unauth / Session |
|---|---|---|---|---|---|---|---|
| AUTH-03/04 Login, OTP | Inline button loading | — | Inline field errors | "Needs internet" | — | — | Session-expired entry point |
| AUTH-06…10 Registration | Step-level | — | Step-level | Blocked from OTP step: "Needs internet" | Progress kept locally | Camera flow at face step | — |
| FRM-01 Dashboard | Skeleton per card | "Add your first produce" | Per-card | Stale everything | Top-bar chip | — | D |
| FRM-04/05/06 Produce | Upload progress per slot | "No produce added yet" | Upload failed → Retry per slot | Draft creation works | **Core case:** draft/pending upload/failed chips | Camera | D |
| FRM-07…11 Market | **Scan line** on analysis | "No market data for {crop}" | "Unable to load live market data. Showing last synchronized information." | Stale + `Last synced` | Alert creation queued | — | D |
| FRM-12…14 Buyers | Scan line (matching) | "No buyers match these filters" | D | Saved buyer info Stale | — | — | D |
| SHR-03/04 Offers, Negotiation | D | "No active offers…" | "Offer no longer available" | Read-only; actions "Needs internet" | Never queued | — | D |
| SHR-05 Agreement | D | — | Verification/creation failure with retry | Read-only | — | Camera (via SHR-07) | D |
| SHR-06 Order Details | D | — | D | Cached read-only | — | — | D |
| FRM-16 Logistics | Provider list loading | "No transport providers are available right now." | D | Saved transport info Stale; booking disabled | — | — | D |
| FRM-17/18 Storage | Scan line on analysis | "No storage matches this crop." | D | Saved storage info Stale; request disabled | — | — | D |
| SHR-08 Tracking | D | "Delivery has not started" | Last known location | Last known location + time | Stage updates: **Q34** | Location (transporter) | D |
| SHR-09 Payment | Processing state | — | Failed state | Waiting for confirmation (never success) | Never queued | — | Session expiry mid-payment shows status after re-login |
| SHR-10/11 Receipt, History | D | "No transactions yet" | D | Cached read-only | — | — | D |
| SHR-01 Notifications | D | "No notifications yet" | D | Cached readable | — | Notification permission | D |
| SHR-14 Grievances | D | "No issues reported" | D | Read cached; submit may queue | Queued grievance chip | — | D |
| TRN-03/06 Requests, Navigation | D | "No requests right now" | D | Accept/stage disabled (**Q34**) | — | Location | D |
| STG-04 Requests | D | "No storage requests yet" | D | Confirm disabled | — | Camera (verification) | D |
| ADM-* | D | Per list | D | Stale, read-only | — | — | Generic "This page isn't available" |

### 13.3 Error catalogue

Errors say **what happened** and **what to do**, never blame the user, never show stack traces or raw codes on the main view (codes live under "Details").

| Kind | Title | Guidance | Actions |
|---|---|---|---|
| Network | "No internet connection" | "Check your connection. Saved information is still available." | Retry · View saved information |
| Timeout / slow | "This is taking longer than usual" | "Your connection may be slow. Try again in a moment." | Retry |
| Server | "Something went wrong on our side" | "Please try again. If it continues, contact support." | Retry · Help |
| Not found / expired | "This is no longer available" | "The offer, lot or order may have changed." | Go back |
| Validation | Inline text under the field | Says exactly what to fix, e.g. "Enter quantity in kg." | — |
| Conflict | "This changed while you were working" | Shows what changed. | Refresh · Edit |
| Verification failed | Per §9.2 | Reason category, no scores | Try again · Cancel |
| Payment failed | Per SHR-09 | "Payment did not complete. Check your account before trying again." | Try again · Choose another method |
| Unauthorized / session | Per §9.6 | — | Go to Home · Verify number |

### 13.4 Empty-state copy library

| Screen | Title | Guidance | CTA |
|---|---|---|---|
| My Crops | No produce added yet | Add your produce to compare markets and find buyers. | Add produce |
| Offers (farmer) | No active offers | Once buyers respond to your produce lot, offers will appear here. | View buyers |
| Offers (buyer) | No offers yet | When farmers respond to your requirements, offers will appear here. | Add requirement |
| Buyer discovery | No buyers match these filters | Try removing a filter. | Clear filters |
| Market | No market data for {crop} yet | Check again later or choose another crop. | Choose crop |
| Logistics | No transport providers are available right now | Please try again later. | Try again |
| Storage | No storage matches this crop | Try another crop or a different duration. | Change crop |
| Orders / History | No transactions yet | Active and completed orders appear here. | View buyers |
| Notifications | No notifications yet | We will tell you about offers, orders, deliveries and prices. | — |
| Alerts | No alerts yet | Add an alert to be told when a price or buyer demand changes. | Add alert |
| Sync status | Everything is synced | Last synced 10:30 AM. | — |
| Transport requests | No requests right now | You will be alerted when a delivery request arrives. | — |
| Storage requests | No storage requests yet | Requests from farmers will appear here. | — |

### 13.5 Loading-copy library

"Loading market prices…" · "Analysing nearby markets…" · "Comparing markets…" · "Matching buyers…" · "Checking your entry…" · "Verifying identity…" · "Sending offer…" · "Sending report…" · "Processing payment…" · "Syncing 3 changes…". Ellipsis-terminated, present-tense, plain.

---

## 14. Content and interaction rules

### 14.1 Tone and language level

- Short sentences (aim ≤ 15 words), everyday words, active voice, second person ("Your produce").
- One idea per sentence; numbers next to their units; no jargon without an info sheet ("modal price", "arrivals", "APMC" style terms get a one-tap explanation).
- Do not use humour, slang, emoji or exclamation marks in system copy.

### 14.2 Confirmation dialogs (examples)

| Action | Title | Body | Confirm / Cancel |
|---|---|---|---|
| Accept offer | Accept this offer? | "₹29/kg for 4,000 kg. The price and quantity will be locked after you accept." | Accept offer / Cancel |
| Reject offer | Reject this offer? | "This cannot be undone." | Reject offer / Cancel |
| Book transport | Book this transport? | "Cost ₹8,000. This reduces your estimated net realization." | Book transport / Cancel |
| Confirm receipt | Confirm you received the produce? | "You will be asked to verify your identity." | Continue to verification / Cancel |
| Pay | Pay ₹1,16,000? | "This is the locked amount for order MM-ON-000124." | Pay now / Cancel |
| Report | Report this transaction? | Per §9.3 | Report transaction / Cancel |
| Delete draft | Delete this draft? | "It has not been sent to buyers." | Delete draft / Cancel |
| Sign out (pending sync) | Sign out? | "3 changes have not synced yet." | Sync first / Sign out anyway |
| Decline request | Decline this request? | "The farmer will be told." | Decline / Cancel |

### 14.3 Interaction rules

- **Irreversible = confirmed**, and the button names the action.
- **Locked = read-only text**, never a disabled input (§9.5).
- **Disabled controls always show a reason** in text.
- **Numbers never change unit or format between screens** (§4.7).
- **Selected states** are shown by border + check icon + tint + `selected` semantics — never colour alone.
- **Lists** show newest/most-urgent first and always name their sort order.
- **Pull-to-refresh** is available on every data list; refresh results update `Updated` captions.
- **No modal stacking:** a dialog never opens another dialog.

---

## 15. Hand-off notes for Compose implementation

This document defines behaviour; it does not prescribe code. To keep implementation faithful:

1. **Tokens first.** Implement `MittiTheme` (colours §4.1, type §4.2, shapes §4.4, spacing §4.3) before any screen. Disable M3 tonal elevation and dynamic (wallpaper) colour so brand colours are never overridden.
2. **One formatter.** Money, price, quantity, percentage, date/time and spoken forms live in one tested module (§4.7). No screen formats numbers.
3. **One source of provenance.** Use `ProvenanceChip`, `LockedValueRow`, `SyncStatusChip`, `ScanLine` for their purposes only.
4. **UiState contract.** Screens render §3.3 states; `Content` always carries `asOf` + `freshness`.
5. **Previews.** Every component ships previews at 320 dp, 200 % font scale, a long-string locale, and each state.
6. **Semantic tests.** Accessibility tests assert content descriptions for money/units, heading roles, and 48 dp targets.
7. **String resources only.** No hard-coded copy; no concatenated sentences (§3.6).
8. **Open questions.** Where a screen cites a **Q**, implement the stated default behind a single switch so the answer can change without redesign.

---

## Appendix A — Self-review log

Five reviews were performed after drafting. Structural checks (code fences, Q-references, screen-ID and § cross-references, unit/wording searches, contrast maths) were run by script against this file; findings are recorded honestly, including errors in earlier drafts of this document.

### A.1 Review 1 — Requirements coverage

- Every section of the brief was mapped to a stable ID in **§2.1** (39 requirement rows) and to a designed location.
- Every screen named in the brief's screen groups has a specification: Authentication 6 (Splash, Language, Login, Registration ×5 roles, OTP, Role Selection), Farmer 28, Buyer 11, FPO 10, Transport 8, Storage 8, Admin 11 — with shared screens defined once (SHR-01…14).
- **Gaps found:** four surfaces that confirmed requirements need but the screen list omits — **Weather**, **Price & Demand Alerts**, **Sync Status**, **Send Offer**. All were added and are marked in §2.2 (none is a new feature).
- All ten states are defined (§13.1) and applied per screen group (§13.2).

### A.2 Review 2 — Contradictions and ambiguities in the brief, and how each was resolved

| # | Issue | Resolution |
|---|---|---|
| 1 | **Onboarding order.** Farmer steps start with mobile/OTP, but a role must be known to run the right flow; "Role Selection" is listed after "OTP" in the screen list. | Login needs no role. **Create account → Role Selection → role flow (mobile → OTP → …).** [D] |
| 2 | **"Quantity must be kg" vs market arrival quantity** (market totals are naturally tonnes/quintals). | kg everywhere, Indian grouping; the data layer converts; the original unit appears only in a source-details sheet. [D] |
| 3 | **Brand fonts lack Indic scripts** — 10 of 11 required languages would render in system fallbacks unpredictably. | Brand fonts for Latin text/digits; declared Noto Sans fallbacks per script; rupee-glyph verification item; APK-size decision **Q16**. [D] |
| 4 | **Contact reveal** — "farmer contact… per the transaction rules" (rules undefined). | Farmer number shown at agreement per backend visibility flag; other parties' visibility **Q2**. Reveal happens *before* both parties verify — consequence documented. |
| 5 | **Report statuses omit "Fraud Confirmed"** yet the brief forbids showing it "unless Admin has confirmed". | Four statuses as specified; "Fraud Confirmed" only via an explicit backend admin outcome, wording backend-supplied (**Q7**). |
| 6 | **Face verification is internet-dependent** but also part of onboarding; the actions that need it are not listed; no path for users who cannot complete it. | Online-only, never queued (**Q4**); action list carried from prior spec (**Q3**); attempt limits and alternative path (**Q30**). |
| 7 | **"Recommendation" is a required data type** while the brief bans AI claims, crop recommendations and weather AI. | Recommendation = a labelled, basis-explained suggestion of a *market/buyer option* from current data; always with "Based on current market information" and "Why this option?"; weather advice is backend-supplied, never generated on device. |
| 8 | **Admin screens are in the Android app** but Admin must not be a public option. | Same login, server-assigned role, no public trace; non-admins see a generic "isn't available" (**Q6**). |
| 9 | **Net-realization example differs from earlier prototype numbers.** | The brief's example is used as the canonical illustration; examples are declared illustrative. |
| 10 | **"Reliability information" vs "never invent ratings or trust scores".** | Only factual, defined fields from the backend; otherwise "Information not available" (**Q8**). |
| 11 | **Price down shown in colour** could collide with "Danger = errors only". | Price decrease uses a Clay arrow icon + sign + text; Danger stays for errors/warnings. [D] |
| 12 | **"One primary CTA per screen" vs the neutral Sell-now/Storage decision.** | Documented exception: two equal-weight outlined actions so neither is implied as advice (FRM-18). [D] |
| 13 | **Farmer "nearby markets" vs location permission.** | Nearby is computed from the registered village, so farmers/buyers never see a location prompt (A4). |
| 14 | **Low-bandwidth mode is required but undefined.** | Defined as automatic + manual Data saver with concrete behaviours (§6.5). [A] |
| 15 | **Backend named "NCP/NPC server"** is undefined. | UI depends only on repository interfaces (**Q1**). |
| 16 | **Locked "final amount cannot be edited" vs a payment that may need bank references.** | Amount always read-only text; bank-transfer input (if any) never touches the amount (**Q10**). |

### A.3 Errors found and fixed in this document's own drafts

| Issue found | Fix |
|---|---|
| Screen-ID collision: Weather and Market Comparison both numbered FRM-09 in early cross-references. | Renumbered FRM-01…19; all cross-references rewritten and re-verified (0 undefined IDs). |
| Principle 1 said "no quintal or tonne anywhere" while §4.7 allowed a source-unit disclosure. | Principle and unit table now state the single exception. |
| Two dashboard descriptions used "best", which §5.4 forbids. | Replaced with "highest estimated net" / "highest nearby price". |
| "NEW DELIVERY REQUEST" in capitals violated the no-uppercase rule for Indic scripts. | Sentence case. |
| "One primary CTA" rule was stated without its FRM-18 exception. | Exception written into principle 5 and §3.2. |
| Clarification items Q29–Q35 were referenced but not defined; Q12 and Q32 were defined but unreferenced; two loose references ("Q24-adjacent", "addendum"). | All defined and referenced (0 undefined, 0 unreferenced Q). |
| `DangerTint` hex was mis-rounded (`#F2E3E0`). | Corrected to `#F1E3E0` (12 % Danger over Paper). |
| Contrast claims were estimates. | Recomputed: Ink/Paper 14.5, Muted/Paper 4.9, Muted/Paper Deep 4.5, Paper/Moss Green 9.3, Moss Light/Paper 4.7, Danger/Paper 5.6, Ink/Wheat 7.0, **Clay/Paper 4.49 (below 4.5)**, **Wheat/Paper 2.07**, Border/Paper 1.3. Usage rules already forbid Clay small text, Wheat text and light-on-Wheat; Moss Light on MossTint measures 3.99, so badge text uses Moss Green. |

### A.4 Review 3 — UI/UX quality

- **Dashboard crowding:** controlled by a density budget (≤ 6 sections, ≤ 3 primary data points per card, conditional strips) and a single primary card above the fold (FRM-01).
- **Primary actions:** each screen names one; multi-action screens were reduced to a sticky bar plus at most two secondaries.
- **Financial visibility:** net realization is the largest figure on OpportunityCard, MarketComparisonCard, Agreement and Order Details; a partial net is never shown with a silently missing deduction (§5.2).
- **Forecast labelling:** three independent cues (container, chip with icon, ranged wording) plus a mandatory disclaimer; forecasts show target dates and expire.
- **Errors/empty/offline:** plain-language catalogue (§13.3), empty copy per screen (§13.4), disabled controls always state a reason.
- **Phone realism:** 320 dp/200 % text envelope, no FABs, drawer for secondary destinations, no tables (stacked cards).
- **Complexity:** two-step confirmations only for irreversible actions; registration is one task per step with saved progress; Add Produce autosaves.

### A.5 Review 4 — Design system consistency

- **Colour:** exactly ten brand hexes plus four documented tints; no white/black; Clay is never a button fill or small-text colour.
- **Typography:** one scale; Plex Mono restricted to the specified data kinds; no all-caps; Indic profile with 1.5× line height.
- **Shape:** radii 12 / 10 / 6 dp only (cards, buttons/fields, badges); no pills; elevation 0 everywhere; borders 1 dp.
- **Spacing:** 4-dp scale, 16-dp margins, 48-dp targets.
- **Navigation:** ≤ 5 bottom destinations per role; same top-bar structure for all roles.
- **Status:** one catalogue; every status has icon + text + tone.

### A.6 Review 5 — Invented features audit

- Text search confirms every occurrence of "AI", "rating", "score", "trust", "voice", "blockchain", "gamification" and "crop recommendation" is a **prohibition**, not a feature.
- Items that go beyond the literal brief are each tagged: **[A]** Data-saver switch, break-even price (removable), Open/Closed requirement status, notification preferences by type, price-alert conditions, "Show expired forecasts"; **[D]** Deals hub, added screens (§2.2); **[P]** items carried from earlier project context; and **35 Q-items** where behaviour is undefined.
- Not designed because not specified: free-text chat, transporter/storage ratings, proceeds sharing between FPO members, admin user suspension, receipt export, dark theme.

---

## Appendix B — Final validation checklist

| Item | Result | Where |
|---|---|---|
| MittiMandi name correct | ✔ | Title |
| Tagline correct | ✔ | Title, AUTH-01 |
| Native Android explicit | ✔ | Header, §3 |
| Kotlin / Compose respected | ✔ | §3.1, §15 |
| Five public roles | ✔ | AUTH-05 |
| Admin protected | ✔ | §9.4, §12.7 |
| Farmer onboarding | ✔ | AUTH-06 |
| Buyer onboarding is different | ✔ | AUTH-07 |
| FPO / Transport / Storage | ✔ | §12.4–12.6 |
| Quantity kg; price ₹/kg | ✔ | §4.7 |
| Sample photo mandatory; lot photo mandatory; video optional | ✔ | FRM-05 |
| Negotiation | ✔ | SHR-04, §11.5 |
| Contact reveal after agreement | ✔ | §9.5, SHR-05 |
| Price / quantity lock; amount auto-calculated | ✔ | SHR-05, LockedValueRow |
| Net realization; transport and storage cost | ✔ | §11.4 |
| Market comparison | ✔ | FRM-09 |
| Forecast clearly labelled | ✔ | §5.1, FRM-10 |
| Weather | ✔ | FRM-15 |
| Buyer discovery | ✔ | FRM-12 |
| Delivery tracking | ✔ | SHR-08 |
| Offline; low-bandwidth; sync states | ✔ | §6 |
| Multilingual | ✔ | §7 |
| Face verification | ✔ | §9.2, SHR-07 |
| Reporting; suspicious ≠ confirmed fraud | ✔ | §9.3, ADM-08 |
| Payment states | ✔ | SHR-09 |
| Loading / empty / error / sync states | ✔ | §13 |
| Accessibility | ✔ | §8 |
| Exact colours; typography | ✔ | §4.1, §4.2 (with Indic fallback) |
| No glassmorphism / neon / futuristic UI / fake AI / fake ratings | ✔ | §4, §5.4–5.5 |
| No invented features | ✔ with tagged additions | Appendix A.6 |

---

## Appendix C — Decisions needed first

These open items block or reshape the most screens. All have a working default in this document.

1. **Q1** — Define the "NCP/NPC server" (auth, sync contract, error model).
2. **Q2** — Exact contact-reveal rules (who sees whose number).
3. **Q3 / Q4 / Q30** — Which actions need face verification; offline behaviour; attempt limits and an alternative for users who cannot complete it.
4. **Q6** — How Admin signs in and whether Admin is in the same app.
5. **Q7** — Report outcomes and the conditions for any "confirmed" wording.
6. **Q10** — Payment flow: who pays whom and when; bank-transfer handling; transport/storage payouts.
7. **Q13 / Q33** — FPO–farmer linking, on-behalf selling, bulk-lot rules.
8. **Q15 / Q19** — Notification delivery when the app is closed; map/navigation provider.
9. **Q16** — Minimum Android version, APK budget, Indic font packaging, dark theme.
10. **Q14** — Crop list and image assets.

---

## Appendix D — Glossary

| Term | Meaning in this document |
|---|---|
| **Actual** | Reported or entered data (published market price, entered quantity, locked/agreed value, confirmed cost). |
| **Forecast** | A predicted future value, always a range with a target date; never guaranteed. |
| **Estimate** | A calculated value using inputs that may themselves be estimates (prefixed `≈`). |
| **Recommendation** | A labelled suggestion of an option with its basis; never a verdict or guarantee. |
| **Net realization** | Gross sale value minus transport, storage and other agreed costs — what the seller actually receives. |
| **Modal price** | The most common trading price in a market. |
| **Arrivals** | Quantity of a crop brought to a market (shown in kg). |
| **Lot** | A quantity of one crop offered for sale with two mandatory photos. **Bulk lot:** a lot an FPO assembles from member produce. |
| **Seller** | A Farmer or an FPO acting on a lot. |
| **FPO** | Farmer Producer Organisation. |
| **Taluk** | Sub-district administrative unit, part of the location hierarchy. |
| **Open to negotiation** | A Yes/No choice by each party; counter offers occur only if both are Yes. |
| **Locked** | Read-only after agreement: price, quantity and amount. |
| **Stale** | Cached data that is offline, failed to refresh, or older than its freshness window; always labelled with its last-synced time. |
| **Deals** | Umbrella navigation destination for offers → negotiation → orders → history. |
| **Data saver** | Manual or automatic low-bandwidth behaviour (§6.5). |
| **Provenance** | Which of the four data types a number is, with source and time. |
