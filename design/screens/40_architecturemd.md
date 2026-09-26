# MittiMandi --- Frontend Architecture

## 1. Purpose

This document defines the frontend architecture for the MittiMandi
Android application.

**Source of truth hierarchy**

1.  `prd.md` --- what the product must do.
2.  `design.md` --- how the product must look and behave.
3.  `architecture.md` --- how the frontend is structured.
4.  `rules.md` --- implementation constraints.
5.  `tasks.md` --- implementation order and checklist.
6.  `memory.md` --- durable project context for AI/coding agents.

The frontend must not invent product behaviour that is absent from the
PRD or design source.

## 2. Platform

-   Native Android.
-   Kotlin.
-   Jetpack Compose.
-   Material 3 as the component foundation.
-   Portrait-first mobile UI.
-   Reference width: 360 dp.
-   Must remain usable at 320 dp.
-   Large-screen content is capped at approximately 600 dp and centred.
-   Edge-to-edge with system insets handled correctly.

## 3. Architecture Pattern

Use a layered architecture:

``` text
UI / Compose
    ↓
ViewModel / UI State
    ↓
Use Cases
    ↓
Repository Interfaces
    ↓
Data Sources
    ├── Remote API
    └── Local Cache / Offline Store
```

Recommended package structure:

``` text
app/
  navigation/
  core/
    ui/
    theme/
    localization/
    connectivity/
    sync/
    error/
    formatting/
    permissions/
  data/
    remote/
    local/
    repository/
    dto/
  domain/
    model/
    repository/
    usecase/
  feature/
    auth/
    farmer/
    buyer/
    fpo/
    transport/
    storage/
    admin/
    shared/
```

## 4. UI Architecture

Each screen follows:

``` text
Route
 └── Screen
      ├── TopBar
      ├── ConnectivityBanner
      ├── Content
      └── StickyActionBar
```

Rules:

-   Screens are stateless where practical.
-   Screens render `UiState`.
-   Screens emit `UiEvent`.
-   ViewModels own screen state and event handling.
-   Business calculations do not happen inside composables.
-   One dominant primary CTA per screen.
-   Avoid unnecessary floating action buttons.

## 5. State Model

Every screen combines one content state with independent overlays.

### Content

``` kotlin
Loading
Content(data, freshness)
Empty(reason)
Error(kind, retryable)
```

### Freshness

``` text
Fresh
Stale
Unknown
```

### Connectivity

``` text
Online
Slow
Offline
```

### Sync

``` text
Synced
Pending
Syncing
Failed
```

### Session

``` text
Active
Expired
```

### Authorization

``` text
Allowed
Unauthorized
```

Offline cached content must remain visible:

``` text
Offline + cached data = Content(Stale) + offline banner
```

It must not become a generic error screen.

## 6. Data Flow

Use unidirectional data flow:

``` text
User action
   ↓
UiEvent
   ↓
ViewModel
   ↓
Use Case
   ↓
Repository
   ↓
Remote/Local data
   ↓
Domain model
   ↓
UiState
   ↓
Composable
```

## 7. Domain Formatting

The UI must not calculate:

-   net realization;
-   gross sale value;
-   transaction totals;
-   break-even values;
-   rating averages;
-   forecast values.

These must arrive from domain/application logic.

Market/decision values require:

``` text
value
unit
type
asOf
sourceLabel
targetDate (when applicable)
basis (when applicable)
```

Supported value types:

``` text
Actual
Forecast
Estimate
Recommendation
```

Missing provenance must render:

> Information not available

## 8. Navigation

Use a single navigation graph with role-aware destinations.

Screen prefixes:

``` text
AUTH-
FRM-
BYR-
FPO-
TRN-
STG-
ADM-
SHR-
```

Primary role navigation:

### Farmer

``` text
Home
My Crops
Market
Buyers
Deals
```

### Buyer

``` text
Home
Requirements
Lots
Deals
Payments
```

### FPO

``` text
Home
Farmers
Lots
Market
Deals
```

### Transport

``` text
Home
Requests
Deliveries
Vehicles
Payments
```

### Storage

``` text
Home
Storage
Requests
Active
Payments
```

### Admin

``` text
Home
Verification
Transactions
Suspicious
```

## 9. Feature Boundaries

### Authentication

Owns:

-   language;
-   login;
-   OTP;
-   role selection;
-   registration;
-   session state.

### Farmer

Owns:

-   farm profile;
-   crops;
-   lots;
-   market comparison;
-   buyers;
-   offers;
-   transactions.

### Buyer

Owns:

-   requirements;
-   lot discovery;
-   offers;
-   negotiation;
-   orders;
-   payment.

### FPO

Owns:

-   farmer management;
-   aggregation;
-   lots;
-   market;
-   buyers;
-   transactions.

### Transport

Owns:

-   vehicles;
-   requests;
-   deliveries;
-   tracking;
-   payment records;
-   ratings received.

### Storage

Owns:

-   facility;
-   capacity;
-   requests;
-   active storage;
-   payments.

### Admin

Owns protected operational screens only.

## 10. Shared Components

Build reusable components for:

-   PriceCard
-   MarketCard
-   MarketComparisonCard
-   MarketSignalCard
-   MoneyPath
-   DecisionStrip
-   OfferLadder
-   NetRealizationCard
-   OpportunityCard
-   MarketCompass
-   MarketPulse
-   BuyerCard
-   OfferCard
-   TransactionCard
-   Timeline
-   DeliveryTrackingCard
-   OfflineBanner
-   SyncStatus
-   RatingSummary
-   RatingInput
-   RatingCard
-   RateAction
-   VerifiedBadge
-   FreshnessIndicator
-   CostBreakdown
-   EmptyState
-   ErrorState
-   LoadingState
-   StickyActionBar

Do not create multiple components that represent the same visual concept
without a documented reason.

## 11. Rating Architecture

Supported relationships:

``` text
Farmer → Buyer
Farmer → Transport Provider
Buyer → Transport Provider
```

Not supported:

``` text
Buyer → Farmer
```

Ratings are tied to completed transactions.

Rating average is calculated by backend/domain logic.

The UI receives:

``` text
average
count
reviews
eligibility
submissionState
```

The UI must not invent or locally calculate the average.

## 12. Offline Architecture

Use a local persistence layer for:

-   cached market information;
-   own profile;
-   drafts;
-   saved buyer/transport/storage information;
-   transaction history;
-   receipts;
-   pending safe operations.

Online-only actions include:

-   fresh prices;
-   new offers;
-   negotiation;
-   payment;
-   live tracking updates;
-   OTP;
-   face verification.

Never silently queue an operation that could cause an unsafe financial
or transaction-state conflict.

## 13. Synchronization

``` text
Local draft
   ↓
Pending
   ↓
Uploading
   ↓
Synced
```

Failure:

``` text
Sync failed
→ retain local data
→ show retry
```

Server-authoritative locked transaction values must not be overwritten
by stale local state.

## 14. Image and Camera Architecture

Camera features must use explicit states:

``` text
Permission
→ Camera
→ Position guidance
→ Capture
→ Processing
→ Success / Failure
```

Face verification must never expose face-match scores.

Mandatory lot photos must be validated before buyer visibility.

## 15. Localization Architecture

Exactly six languages:

-   English
-   Hindi
-   Marathi
-   Kannada
-   Telugu
-   Tamil

All strings must come from resources.

Never hard-code user-facing text inside composables.

Never place language-specific text inside images.

Layouts must support text expansion.

## 16. Theme Architecture

The UI uses the approved light palette from `design.md`.

Core identity:

**Sky Blue + Burnt Orange + Market Amber + warm light neutrals**

No green.

No dark theme.

No black-heavy surfaces.

Theme tokens must be centralised and not repeated as raw hex values
across feature code.

## 17. Error Handling

Use typed error states.

Examples:

``` text
Network
Timeout
Server
NotFound
Validation
Conflict
Unknown
```

Error UI must provide an actionable recovery where possible.

Never claim success when the backend has not confirmed success.

## 18. Testing Architecture

Minimum testing layers:

``` text
Unit
→ Use Cases
→ ViewModels
→ Repository
→ Compose UI
→ Navigation
→ Offline/Sync
```

Critical scenarios:

-   offline cached market data;
-   stale data;
-   sync failure;
-   locked transaction;
-   failed payment;
-   duplicate rating;
-   rating eligibility;
-   localization expansion;
-   320 dp layout;
-   200% font scaling.
