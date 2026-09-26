# MittiMandi --- Product Requirements Document (PRD)

**Tagline:** Know the Market. Choose Better. Sell Smarter.

  Field                     Value
  ------------------------- --------------------------------------
  Product                   MittiMandi
  Version                   1.0
  Status                    Product Requirements Baseline
  Date                      21 September 2026
  Platform                  Native Android
  Primary users             Farmers, Buyers, FPOs
  Supporting roles          Transport Provider, Storage Provider
  Operational role          Admin
  Related source of truth   `design.md`

## 1. Product Overview

### 1.1 Product definition

MittiMandi is a farmer-first agricultural market-intelligence and
transaction platform for Android.

It helps users move from seeing a headline market price to understanding
the practical selling decision:

**Crop → Market → Price → Demand → Buyer → Quality → Logistics → Storage
→ Transaction → Payment**

The core product question is:

> **If I sell this crop today, where should I sell it, to whom, at what
> price, and after transport, storage and other legitimate agreed costs,
> how much will I actually receive?**

### 1.2 Problem

Farmers and FPOs may have difficulty comparing current prices, expected
prices, buyer demand, quality requirements, transport costs, storage
costs, payment reliability and actual net realization. Buyers may also
struggle to aggregate suitable volumes and verify transaction
information.

MittiMandi brings market intelligence and transaction enablement into
one workflow.

### 1.3 Goals

-   Improve selling decisions using price and net realization.
-   Improve visibility into nearby and comparable markets.
-   Connect farmers/FPOs with relevant buyers.
-   Enable structured offers and negotiation.
-   Lock agreed price, quantity and amount after agreement.
-   Coordinate transport, delivery, storage and payment.
-   Maintain a digital transaction record.
-   Remain useful in rural, unreliable-connectivity conditions.
-   Support exactly six languages.
-   Provide factual verification and transaction-based ratings without
    inventing trust scores.

## 2. Non-Goals

V1 does not include:

-   Free-text chat.
-   Separate trust scores.
-   Artificial "Best", "Top" or "Trusted" labels.
-   Buyer → Farmer ratings.
-   Blockchain.
-   Social feed.
-   Gamification.
-   Voice assistant.
-   Guaranteed forecasts.
-   Automatic fraud confirmation.
-   Web/desktop product.
-   Dark theme.
-   AI-generated crop recommendations.
-   Unsupported payment-provider claims.

## 3. Roles

  -----------------------------------------------------------------------
  Role                                Main responsibility
  ----------------------------------- -----------------------------------
  Farmer                              Create produce lots, compare
                                      markets, discover buyers, negotiate
                                      and sell

  Buyer                               Define requirements, discover lots,
                                      negotiate, purchase and pay

  FPO                                 Manage farmers and aggregate
                                      produce

  Transport Provider                  Accept and complete delivery
                                      requests

  Storage Provider                    Manage capacity and storage
                                      bookings

  Admin                               Protected operational review and
                                      administration
  -----------------------------------------------------------------------

Admin is never a public registration option.

## 4. Product Principles

1.  **Farmer-first:** optimise the primary workflow for simplicity.
2.  **Money first:** prices use `₹/kg`; quantities use `kg`.
3.  **Net realization first:** show what the seller may actually receive
    after known costs.
4.  **Truthful labels:** every applicable value is Actual, Forecast,
    Estimate or Recommendation.
5.  **Freshness:** cached information always shows last synchronization
    time.
6.  **One primary action:** normally one primary CTA per screen.
7.  **Plain language:** short, localizable copy.
8.  **Security is calm:** face verification is an identity step.
9.  **Trust is factual:** verification and ratings are separate.
10. **Rural-first:** support small screens, large text and unreliable
    connectivity.

## 5. Core Journey

### 5.1 Farmer

``` text
Register
→ Add produce
→ Upload mandatory photos
→ View market prices
→ Compare markets
→ View demand/opportunities
→ Discover buyers
→ Check buyer requirements
→ Send offer
→ Negotiate
→ Agreement
→ Lock price/quantity/amount
→ Face verification
→ Order
→ Book transport
→ Delivery
→ Payment
→ Receipt
→ Completed
→ Rate buyer / transporter
```

### 5.2 Buyer

``` text
Register
→ Define requirements
→ Discover lots
→ Offer / negotiate
→ Agreement
→ Face verification
→ Order
→ Delivery
→ Confirm receipt
→ Pay
→ Receipt
→ Rate transporter
```

### 5.3 Transport

``` text
Register
→ Add vehicle
→ Receive request
→ Accept
→ Navigate
→ Pickup
→ Load
→ Transit
→ Buyer
→ Deliver
→ Payment record
```

### 5.4 Storage

``` text
Register
→ Add facility/capacity
→ Receive request
→ Check capacity/crop suitability
→ Confirm
→ Active storage
→ Complete
→ Payment record
```

## 6. Functional Requirements

### 6.1 Authentication and onboarding

**AUTH-01 --- Language:** first launch offers exactly English, Hindi,
Marathi, Kannada, Telugu and Tamil.

**AUTH-02 --- Login:** mobile number + OTP/security verification.

**AUTH-03 --- Registration:** five public roles only; Admin is
server-assigned.

**AUTH-04 --- Farmer:** mobile, OTP, name, basic details, face, state,
district, taluk, village, land area, crops and FPO.

**AUTH-05 --- Buyer:** buyer/business details and purchase requirements.
Buyer does not register by selecting crops they produce.

**AUTH-06 --- FPO:** identity/business details and face capture.

**AUTH-07 --- Transport:** profile, face capture, vehicle, capacity and
availability.

**AUTH-08 --- Storage:** profile, face capture, facility, storage type,
crop suitability, capacity and cost.

### 6.2 Produce and lots

A lot contains:

-   crop;
-   quantity in kg;
-   actual harvest date;
-   Open to Negotiation Yes/No;
-   mandatory single-sample photo;
-   mandatory full-lot photo;
-   optional video.

A lot becomes visible to buyers only after required photos are uploaded.

Draft lots can be saved offline.

### 6.3 Market intelligence

Market module supports, where data is available:

-   current prices;
-   nearby markets;
-   market comparison;
-   min/max/modal price;
-   arrivals;
-   history;
-   trend;
-   tomorrow forecast;
-   7-day forecast;
-   confidence;
-   price alerts;
-   market-opportunity alerts;
-   demand alerts.

Every applicable value shows source and update time.

Forecasts must show:

> Price forecasts are estimates and are not guaranteed future prices.

### 6.4 Net realization

``` text
Gross sale value = Quantity × Price

Net realization =
Gross sale value
− Transport
− Storage
− Other legitimate agreed costs
```

If a required deduction is unavailable, do not silently calculate a
complete net value.

Example:

> Cannot calculate --- transport cost not available

### 6.5 Buyer discovery

Buyer discovery can show:

-   business/name;
-   verification;
-   location;
-   crop;
-   required quantity;
-   quality requirements;
-   expected price range;
-   offers;
-   negotiation status;
-   factual backend-provided reliability information;
-   transaction ratings/reviews.

No invented matching or trust score is allowed.

### 6.6 Offers and negotiation

Flow:

``` text
Offer → Counter offer → Agreement
```

Counter offers are available only when both parties are Open to
Negotiation.

No free-text chat is included in v1.

### 6.7 Agreement

After agreement:

-   price is locked;
-   quantity is locked;
-   amount is locked;
-   amount is calculated automatically.

Example:

`4,000 kg × ₹29/kg = ₹1,16,000`

Locked values are read-only.

The farmer's contact number is revealed after both parties agree
according to the transaction rule.

### 6.8 Transaction lifecycle

``` text
Offer
→ Negotiation
→ Agreement
→ Price Lock
→ Quantity Lock
→ Face Verification
→ Order Created
→ Transport
→ Delivery
→ Payment
→ Receipt
→ Completed
→ Rating Available
→ Rating Submitted
```

### 6.9 Face verification

States:

1.  Permission
2.  Camera
3.  Position guidance
4.  Capture
5.  Processing
6.  Success
7.  Failure
8.  Retry

Failure reasons may include:

-   Could not read your face;
-   Face did not match;
-   Network problem;
-   Camera problem.

No face-matching scores are shown.

Offline:

> Face verification needs internet.

### 6.10 Logistics

Transport information includes provider, vehicle, route, ETA, distance,
cost and status.

Delivery stages:

``` text
Accepted
→ Navigating to pickup
→ Reached pickup
→ Produce loaded
→ In transit
→ Reached buyer
→ Delivered
```

Tracking must show last updated time. When stale:

> Showing last known location

### 6.11 Storage

Storage information includes:

-   facility;
-   location;
-   storage type;
-   crop suitability;
-   cost/kg/day;
-   capacity;
-   availability;
-   duration where supplied.

Sell-now vs storage must be presented neutrally.

### 6.12 Payments

Methods:

-   Bank transfer;
-   UPI / online payment.

States:

-   Pending;
-   Processing;
-   Successful;
-   Failed.

Unknown payment state must never be treated as successful.

### 6.13 Receipt/history

Receipt includes:

-   Transaction ID;
-   Order ID;
-   crop;
-   quantity;
-   price;
-   gross;
-   transport;
-   storage;
-   other agreed costs;
-   net seller amount / buyer amount paid;
-   payment method;
-   payment status;
-   timestamp;
-   parties.

History supports Order ID, status, crop, date and reported filters.

## 7. Ratings and Reviews

### 7.1 Rating relationships

  Rater    Rated party          When
  -------- -------------------- -----------------------------
  Farmer   Buyer                After completed transaction
  Farmer   Transport Provider   After completed delivery
  Buyer    Transport Provider   After completed delivery

Buyer → Farmer rating is not supported.

### 7.2 Rating scale

1--5 stars:

-   1 --- Very poor
-   2 --- Poor
-   3 --- Average
-   4 --- Good
-   5 --- Very good

Example:

`4.5 ★ · Based on 24 completed ratings`

If none:

`No ratings yet`

### 7.3 Rating rules

-   Only eligible completed transactions generate ratings.
-   One user can rate a rated party once for the same transaction.
-   Backend calculates averages.
-   Cancelled/incomplete transactions do not generate ratings.
-   Ratings do not change price, payment, order status or transaction
    eligibility.
-   Ratings do not create a separate trust score.
-   No "Best", "Top" or "Trusted" labels based only on ratings.
-   Written feedback is optional.
-   Rating submission normally requires internet unless safe backend
    queuing exists.

### 7.4 Rating states

-   No ratings yet
-   Rating available
-   Rating submitted
-   Rating already submitted
-   Rating submission failed
-   Rating submission pending
-   Ratings unavailable

## 8. Trust and Verification

### 8.1 Verified badge

Verified means:

> MittiMandi verified the submitted identity/business information.

It does not mean financial reliability.

### 8.2 Reliability information

Only factual backend-provided reliability fields may be shown.

Otherwise:

> Information not available

### 8.3 Reports

Report flow:

``` text
Report transaction
→ Confirm
→ Automatic evidence collection
→ Report submitted
→ Review
```

Evidence may include offer, negotiation, order, payment, verification,
transport, storage, delivery status, timestamps and activity log.

Statuses:

`Reported → Suspicious Activity → Under Investigation → Resolved`

The UI must not independently infer fraud.

## 9. Offline and Low-Bandwidth

### 9.1 Offline supported

-   own profile;
-   previously loaded market information as stale;
-   draft lots;
-   saved buyer information;
-   saved transport information;
-   saved storage information;
-   cached transaction history/receipts;
-   received notifications.

### 9.2 Online-only

-   fresh prices;
-   new offers;
-   negotiation;
-   payments;
-   active tracking updates;
-   face verification;
-   OTP/login;
-   other shared time-sensitive state changes.

### 9.3 Required states

-   Offline
-   Last synced
-   Pending synchronization
-   Sync failed

### 9.4 Sync

``` text
Saved locally → Pending synchronization → Uploading → Synced
```

Failed items show Retry.

Server-authoritative locked data cannot be overwritten by offline edits.

### 9.5 Data Saver

Data Saver may:

-   load text before images;
-   compress uploads;
-   prefer unmetered video upload;
-   avoid unnecessary polling;
-   render chart summaries before charts;
-   load map tiles on demand;
-   reduce non-essential motion.

## 10. Multilingual Requirements

Exactly six languages:

  Language   Script
  ---------- ------------
  English    Latin
  Hindi      Devanagari
  Marathi    Devanagari
  Kannada    Kannada
  Telugu     Telugu
  Tamil      Tamil

Rules:

-   flexible text containers;
-   no fixed-width English-only buttons;
-   buttons may wrap;
-   no text embedded in images;
-   full words instead of unexplained abbreviations;
-   string resources for all UI copy;
-   fallback to English when a translation is missing.

## 11. Navigation

### Farmer

Home · My Crops · Market · Buyers · Deals

Secondary: Weather, Logistics, Storage, Alerts, Notifications, Help,
Settings, Profile, Sync Status.

### Buyer

Home · Requirements · Lots · Deals · Payments

### FPO

Home · Farmers · Lots · Market · Deals

### Transport

Home · Requests · Deliveries · Vehicles · Payments

### Storage

Home · Storage · Requests · Active · Payments

### Admin

Home · Verification · Transactions · Suspicious

## 12. Screen Inventory

### Authentication

Splash, Language, Login, OTP, Role Selection, Farmer Registration, Buyer
Registration, FPO Registration, Transport Registration, Storage
Registration.

### Farmer

Dashboard, Profile, Farm Details, My Crops, Add Produce, Produce
Details, Market Dashboard, Current Prices, Market Comparison, Price
Forecast, Market Opportunity, Buyer Discovery, Buyer Profile, Buyer
Requirements, Weather, Logistics, Storage, Storage Analysis, Price &
Demand Alerts.

### Buyer

Dashboard, Requirements, Lots, Offers, Negotiations, Orders, Delivery,
Payments, Transactions, Alerts, Profile.

### FPO

Dashboard, Farmers, Produce, Bulk Lots, Markets, Buyers, Offers,
Logistics, Storage, Transactions, Profile.

### Transport

Dashboard, Vehicles, Requests, Bookings, Deliveries, Navigation,
Payments, Profile.

### Storage

Dashboard, Storage, Capacity, Requests, Bookings, Active Storage,
Payments, Profile.

### Admin

Dashboard, Users, Verification, Markets, Transactions, Payments, Offers,
Suspicious Activity, Grievances, Reports, Settings.

### Shared

Notifications, Settings, Offers, Negotiation, Agreement, Order Details,
Face Verification, Delivery Tracking, Payment, Digital Receipt,
Transaction History, Sync Status, Send Offer, Help & Grievances.

## 13. Data Requirements

### Farmer

User ID, mobile, name, location hierarchy, land area, crops, FPO, face
status, language.

### Lot

Lot ID, crop, quantity, harvest date, photos, optional video,
negotiation preference, seller, status, timestamps, sync state.

### Market

Market, crop, current/min/max/modal prices, arrivals, history, trend,
forecast, target date, confidence, source, update time.

### Buyer

Buyer ID, business, location, verification, crop requirements, quantity,
quality, expected price, factual reliability fields, ratings and
reviews.

### Transport

Provider ID, name/business, vehicle, vehicle number, capacity,
availability, cost, verification, ratings and reviews.

### Storage

Provider ID, facility, location, type, crop suitability, capacity,
availability, cost, duration, verification.

### Transaction

Transaction ID, Order ID, parties, crop, quantity, price, gross,
transport, storage, other costs, net, payment, delivery, timestamps,
audit log, report state, rating eligibility.

### Rating

Rating ID, transaction ID, rater, rated party, 1--5 value, optional
review, timestamp, moderation state.

## 14. Business Rules

  -----------------------------------------------------------------------
  ID                                  Rule
  ----------------------------------- -----------------------------------
  BR-01                               Prices use ₹/kg; quantities use kg

  BR-02                               Price, quantity and amount lock
                                      after agreement

  BR-03                               Amount = quantity × price

  BR-04                               Net = gross − transport − storage −
                                      other legitimate agreed costs

  BR-05                               Counter offers require both parties
                                      to be Open to Negotiation

  BR-06                               Contact reveal follows the
                                      confirmed post-agreement
                                      transaction rule

  BR-07                               Ratings require an eligible
                                      completed transaction

  BR-08                               One rating per rated party per
                                      transaction

  BR-09                               Ratings do not control price,
                                      payment, status or eligibility

  BR-10                               Verification is identity/business
                                      verification, not financial
                                      guarantee

  BR-11                               Forecasts are estimates, never
                                      guarantees

  BR-12                               Shared financial/time-sensitive
                                      actions are online-only unless
                                      safely queued by backend

  BR-13                               User-owned drafts may be stored
                                      offline

  BR-14                               Reports do not automatically mean
                                      fraud

  BR-15                               Admin is not a public role
  -----------------------------------------------------------------------

## 15. Accessibility

The product must support:

-   48 × 48 dp minimum touch targets;
-   appropriate contrast;
-   TalkBack semantics;
-   dynamic text up to 200%;
-   visible focus;
-   logical focus order;
-   status conveyed by icon + text, not colour alone;
-   text alternatives for charts/maps;
-   320 dp width testing;
-   localization expansion testing.

## 16. Visual Product Direction

The approved v1 direction is **light, clear, market-oriented, with no
green and no dark theme**.

Primary identity:

**Sky Blue + Burnt Orange + Market Amber + warm light neutrals**

Suggested tokens:

  Token         Hex
  ------------- -----------
  Canvas        `#F4FAFC`
  Surface       `#FFFFFF`
  BlueMist      `#E2F3F8`
  BlueSoft      `#C7E8F0`
  SkyBlue       `#36AFCB`
  ClearBlue     `#147F9E`
  BurntOrange   `#C96842`
  ClayOrange    `#A95135`
  MarketAmber   `#D29A32`
  Sand          `#FFF3DF`
  Ink           `#193640`
  Slate         `#607780`
  MistText      `#8FA1A7`
  Line          `#D7E7EB`
  Error         `#C64F48`

Do not use:

-   green as brand colour;
-   dark theme;
-   black-heavy UI;
-   neon;
-   glassmorphism;
-   futuristic gradients;
-   excessive glow;
-   excessive shadows.

Reusable product concepts may include Market Signal, Money Path,
Decision Strip, Offer Ladder, Market Compass, Cost Waterfall, Market
Pulse, Transport Journey, Transaction Timeline, Why This Value?, and
Freshness Indicator.

## 17. Product States

Every major screen must support:

1.  Loading
2.  Success
3.  Empty
4.  Error
5.  Offline
6.  Sync pending
7.  Sync failed
8.  Permission denied
9.  Unauthorized
10. Session expired

## 18. Key Success Metrics

Initial product metrics:

-   percentage of active farmers viewing market comparison;
-   percentage viewing net realization before a sale;
-   time from lot creation to buyer discovery;
-   completed transactions;
-   active farmer lots;
-   active buyer requirements;
-   offer creation rate;
-   negotiation completion rate;
-   agreement rate;
-   delivery completion rate;
-   payment completion rate;
-   sync success rate;
-   crash-free sessions;
-   accessibility defects;
-   localization defects;
-   eligible transactions receiving ratings.

Ratings are product feedback and must not be converted into a separate
trust score.

## 19. MVP Scope

### P0

-   Authentication and six-language selection.
-   Five public roles.
-   Farmer produce/lots and mandatory photos.
-   Market prices and comparison.
-   Net realization.
-   Buyer discovery and requirements.
-   Offers and negotiation.
-   Agreement and locked values.
-   Face verification.
-   Orders.
-   Transport and delivery.
-   Storage.
-   Payments and receipts.
-   Transaction history.
-   Ratings.
-   Reporting and grievances.
-   Notifications.
-   Offline drafts and cached data.
-   Sync status.
-   Accessibility.

### P1

-   richer opportunity alerts;
-   enhanced storage analysis;
-   richer historical market views;
-   improved FPO workflows;
-   additional transaction analytics;
-   expanded review moderation.

### Future

Future features require separate approved requirements, validation and
design work. They are not committed v1 functionality.

## 20. Acceptance Criteria

-   [ ] Exactly six languages are available.
-   [ ] Admin is not publicly selectable.
-   [ ] Farmer can create a lot with crop, quantity, harvest date and
    negotiation preference.
-   [ ] Both mandatory photos are required before buyer visibility.
-   [ ] Market values show source/time/provenance.
-   [ ] Market comparison includes net realization where calculable.
-   [ ] Missing required costs never produce a silently incomplete net.
-   [ ] Forecasts show target date and disclaimer.
-   [ ] Buyer requirements support crop, quantity, quality and expected
    price.
-   [ ] Negotiation requires both parties to be open to negotiation.
-   [ ] Agreement locks price, quantity and amount.
-   [ ] Face verification blocks configured critical actions until
    successful.
-   [ ] Delivery follows the defined stage sequence.
-   [ ] Payment has Pending, Processing, Successful and Failed states.
-   [ ] Unknown payment status is never treated as successful.
-   [ ] Receipt contains required financial fields.
-   [ ] Farmer can rate Buyer after a completed transaction.
-   [ ] Farmer can rate Transport Provider after completed delivery.
-   [ ] Buyer can rate Transport Provider after completed delivery.
-   [ ] Buyer cannot rate Farmer.
-   [ ] One rating per rated party per transaction is enforced.
-   [ ] Ratings do not create a trust score.
-   [ ] Offline states are visible.
-   [ ] Shared financial/time-sensitive actions are not silently queued.
-   [ ] Reports do not automatically classify fraud.
-   [ ] Accessibility requirements pass.
-   [ ] UI follows the light Sky Blue + Burnt Orange + Market Amber
    direction with no green and no dark theme.

## 21. Open Product Decisions

Before final implementation, resolve:

1.  Backend authentication and synchronization contract.
2.  Exact contact visibility for each participant.
3.  Exact transaction actions requiring face verification.
4.  Face-verification attempt/failure policy.
5.  Admin authentication/deployment model.
6.  Report outcome vocabulary.
7.  Payment sequence and provider integration.
8.  FPO membership and on-behalf selling rules.
9.  Closed-app notification delivery.
10. Map/navigation provider.
11. Minimum Android version and device baseline.
12. APK/package-size budget.
13. Complete crop list and assets.
14. Weather provider and crop-risk rules.
15. Storage duration/cost rules.
16. Receipt sharing/export.
17. Data freshness windows.
18. Offline transport-stage updates.
19. Rating moderation and review visibility.
20. Rating eligibility window.

## 22. Traceability

`prd.md` defines **what the product must do**.

`design.md` defines **how the Android UI/UX presents and supports those
requirements**.

The two documents must remain synchronized. When a product requirement
changes, the corresponding design requirement, screen, component, state
and acceptance criterion must also be reviewed.

------------------------------------------------------------------------

# Appendix A --- Glossary

  Term                  Meaning
  --------------------- -----------------------------------------------------------
  Actual                Reported or entered data
  Forecast              Predicted future value
  Estimate              Calculated value using available inputs
  Recommendation        Labelled suggestion based on supplied information
  Net realization       Gross sale value minus applicable agreed costs
  Modal price           Most common trading price
  Arrivals              Quantity brought to a market
  Lot                   Quantity of one crop offered for sale
  Seller                Farmer or FPO acting on a lot
  FPO                   Farmer Producer Organisation
  Open to Negotiation   Setting controlling counter offers
  Locked                Read-only after agreement
  Stale                 Cached/outdated information labelled with sync time
  Verified              Submitted identity/business information has been verified
  Rating                Transaction-based 1--5 feedback
  Deals                 Offers → negotiation → orders → history
  Data Saver            Low-bandwidth behaviour
  Provenance            Source, time and data type for a value

# Appendix B --- Core Copy

**Forecast:**\
"Price forecasts are estimates and are not guaranteed future prices."

**Recommendation basis:**\
"Based on current market information"

**Missing data:**\
"Information not available"

**Offline:**\
"Offline. Showing saved information."

**Stale tracking:**\
"Showing last known location"

**Rating empty:**\
"No ratings yet"

**Rating failure:**\
"Rating could not be submitted. Please try again when you are online."

**Suspicious activity:**\
"This transaction has been flagged for review. This is not a finding of
fraud."

# Appendix C --- One-Sentence Product Definition

> **MittiMandi helps farmers and FPOs compare where, to whom and how to
> sell agricultural produce by combining market prices, net realization,
> buyer demand, negotiation, logistics, storage, payment and transaction
> records in one rural-first Android platform.**
