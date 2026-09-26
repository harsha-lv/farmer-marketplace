# MittiMandi --- Frontend Rules

## 1. Authority Rules

-   `prd.md` defines product requirements.
-   `design.md` defines visual and interaction requirements.
-   Do not contradict either document.
-   If a requirement is unclear, do not invent a business rule.
-   Prefer a safe empty/unknown state over fabricated data.
-   Product decisions must be made in the PRD, not hidden inside UI
    code.

## 2. Design Rules

-   Use the approved light visual direction.
-   Primary identity: Sky Blue + Burnt Orange + Market Amber.
-   Green is forbidden as a brand/status colour.
-   Dark theme is not part of v1.
-   Avoid black-heavy UI.
-   No neon.
-   No glassmorphism.
-   No futuristic visual effects.
-   No excessive gradients.
-   No decorative glow.
-   No excessive shadows.
-   No unnecessary animation.

## 3. Layout Rules

-   Design for 360 × 640 dp first.
-   Must remain usable at 320 dp.
-   Use responsive constraints instead of fixed widths.
-   Support 200% system font scale.
-   Do not use fixed-height containers around text.
-   Respect system bars and IME.
-   Use approximately 48 dp minimum touch targets.
-   Keep the primary content column readable.
-   Do not overcrowd dashboards.

## 4. CTA Rules

-   Prefer one dominant primary CTA per screen.
-   Primary CTA must describe the action.
-   Avoid vague labels such as `Continue` when a specific action is
    possible.
-   Do not hide critical actions.
-   Destructive actions require confirmation.
-   Locked transaction values must not appear editable.

## 5. Data Rules

-   Price: `₹/kg`.
-   Quantity: `kg`.
-   Money uses Indian digit grouping.
-   Never mix units without labels.
-   Never display an Actual, Forecast or Estimate without
    freshness/source information.
-   Missing information must say `Information not available`.
-   Cached data must show its freshness state.
-   Forecasts must be clearly labelled as estimates.
-   Never present a forecast as a guaranteed price.

## 6. Calculation Rules

UI composables must not perform business calculations.

Do not calculate in UI:

-   gross sale value;
-   net realization;
-   rating averages;
-   break-even values;
-   forecast values;
-   payment totals.

The UI renders values supplied by domain/application logic.

## 7. Net Realization Rules

The product must distinguish headline price from practical realization.

Conceptually:

``` text
Gross = quantity × price

Net = gross − transport − storage − other legitimate agreed costs
```

If required cost data is missing, do not silently show a complete net
value.

## 8. Trust Rules

-   `Verified` means submitted identity/business information was
    verified.
-   Verified does not mean financially guaranteed.
-   Do not invent trust scores.
-   Do not create `Trusted`, `Best`, or `Top` labels from ratings.
-   Do not show fake reliability values.
-   Do not show fake AI confidence.
-   Do not imply a transaction is safe merely because a user is
    verified.

## 9. Rating Rules

Supported:

``` text
Farmer → Buyer
Farmer → Transport Provider
Buyer → Transport Provider
```

Not supported:

``` text
Buyer → Farmer
```

Rules:

-   Ratings are available only after eligible completed transactions.
-   Scale is 1--5 stars.
-   Written feedback is optional.
-   One rating per rated party per transaction.
-   Backend/domain calculates averages.
-   Always show rating count with the average.
-   No ratings = `No ratings yet`.
-   Ratings do not control transaction eligibility.
-   Ratings do not control price.
-   Ratings do not control payment.
-   Ratings do not control order status.
-   Ratings do not become a separate trust score.
-   Do not show star ratings before an eligible transaction exists.

## 10. Transaction Rules

Required lifecycle:

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

After agreement:

-   price is locked;
-   quantity is locked;
-   amount is locked.

Locked values are read-only.

## 11. Offline Rules

Always make connectivity visible when it affects the current action.

Offline may support:

-   cached information;
-   drafts;
-   safe local records.

Offline must not falsely simulate:

-   payment success;
-   new market price;
-   completed negotiation;
-   face verification;
-   live location;
-   server-confirmed transaction changes.

If an action requires internet, explain it clearly.

## 12. Sync Rules

Display:

-   Last synced;
-   Pending;
-   Syncing;
-   Failed.

Do not silently discard failed local changes.

Do not overwrite server-authoritative locked data with stale local data.

## 13. Localization Rules

Exactly six languages:

1.  English
2.  Hindi
3.  Marathi
4.  Kannada
5.  Telugu
6.  Tamil

Rules:

-   use resource strings;
-   no hard-coded UI copy;
-   no fixed-width English-only controls;
-   allow wrapping;
-   no text inside images;
-   test long translations;
-   provide English fallback for missing translations.

## 14. Accessibility Rules

-   Touch targets approximately 48 dp or larger.
-   Support screen readers.
-   Add content descriptions to meaningful icons.
-   Never communicate status through colour alone.
-   Support dynamic font scaling.
-   Maintain visible focus/selection states.
-   Maintain logical focus order.
-   Avoid dense tables on small screens.
-   Test 200% font scale.

## 15. Security and Privacy Rules

-   Do not log OTPs.
-   Do not log sensitive face-verification data.
-   Do not expose private contact information before the defined
    transaction state.
-   Do not store secrets in source code.
-   API keys belong in secure configuration/backend infrastructure.
-   Do not expose internal admin functions to normal users.

## 16. Navigation Rules

-   Navigation must be role-aware.
-   Users must not access another role's private workflow without
    explicit product support.
-   Back navigation must preserve safe form state where appropriate.
-   Expired sessions must redirect through authentication.
-   Unauthorized screens must not reveal protected information.

## 17. Component Rules

Prefer reusable components for repeated patterns.

Before creating a component:

1.  Search existing shared components.
2.  Check whether a variant is enough.
3.  Only create a new component when the visual/behavioural contract is
    genuinely different.

## 18. Copy Rules

Use plain language.

Prefer:

`Price per kg`

over:

`Unit Rate`

Prefer:

`What you may receive`

over:

`Expected Revenue Realization`

Use precise status language:

-   Pending
-   Processing
-   Successful
-   Failed
-   Verified
-   Verification Pending
-   Verification Failed
-   Reported
-   Under Investigation
-   Resolved

## 19. Anti-Fabrication Rules

Never fabricate:

-   prices;
-   buyers;
-   ratings;
-   market data;
-   transport availability;
-   storage availability;
-   forecasts;
-   payment status;
-   live location;
-   verification results;
-   AI confidence.

If data is absent:

> Information not available

## 20. AI Coding Rules

When generating frontend code:

-   preserve existing architecture;
-   avoid unnecessary dependencies;
-   do not replace the design system;
-   do not introduce another state-management framework without
    approval;
-   do not create duplicate screens;
-   do not change product requirements inside implementation;
-   keep business logic outside composables;
-   write testable code;
-   use meaningful names;
-   keep files focused;
-   document non-obvious decisions.

## 21. Definition of Done

A frontend feature is complete only when:

-   requirement is implemented;
-   design tokens are correct;
-   loading state exists;
-   empty state exists where applicable;
-   error state exists;
-   offline behaviour is defined;
-   sync behaviour is defined where applicable;
-   localization is supported;
-   accessibility is considered;
-   navigation works;
-   tests cover critical logic;
-   no fake data is presented as real data.
