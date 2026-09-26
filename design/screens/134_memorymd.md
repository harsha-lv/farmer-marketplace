# MittiMandi --- Project Memory

## 1. Project Identity

**Product:** MittiMandi

**Tagline:** Know the Market. Choose Better. Sell Smarter.

**Platform:** Native Android

**Primary technology direction:** Kotlin + Jetpack Compose + Material 3

**Primary users:** Farmers, Buyers and FPOs

**Supporting roles:** Transport Provider and Storage Provider

**Admin:** Protected operational role

## 2. Core Product Idea

MittiMandi is not only a mandi-price display app.

Its core purpose is to help a farmer answer:

> If I sell this crop today, where should I sell it, to whom, at what
> price, and after transport, storage and other legitimate agreed costs,
> how much will I actually receive?

Core journey:

``` text
Crop
→ Market
→ Price
→ Demand
→ Buyer
→ Quality
→ Logistics
→ Storage
→ Transaction
→ Payment
```

## 3. Important Product Differentiator

The UI should emphasise **Net Realization**, not only headline price.

Concept:

``` text
Gross sale value
− Transport
− Storage
− Other legitimate agreed costs
= Net realization
```

Missing cost data must not be hidden.

## 4. Visual Memory

The approved visual direction is:

**Light + Sky Blue + Burnt Orange + Market Amber + warm light neutrals**

Must remember:

-   No green.
-   No dark theme.
-   No black-heavy UI.
-   No neon.
-   No glassmorphism.
-   No futuristic styling.
-   No excessive gradients.
-   No excessive glow.
-   No decorative visual noise.

Core visual ideas:

-   Market Signal
-   Money Path
-   Decision Strip
-   Offer Ladder
-   Market Compass
-   Sell Smart / Opportunity Card
-   Cost Waterfall
-   Market Pulse
-   Transport Journey
-   Transaction Timeline
-   Why This Value?
-   Freshness Indicator

These should be implemented as useful UI patterns, not decorative
effects.

## 5. Languages

Exactly six:

1.  English
2.  Hindi
3.  Marathi
4.  Kannada
5.  Telugu
6.  Tamil

No Gujarati, Punjabi, Bengali, Malayalam or Odia in v1.

## 6. Rating Memory

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

Rating rules:

-   1--5 stars.
-   Optional written review.
-   Only after eligible completed transactions.
-   One rating per rated party per transaction.
-   Average calculated by backend/domain.
-   Show rating count with average.
-   No ratings = `No ratings yet`.
-   Ratings are not a trust score.
-   Never label users `Best`, `Top` or `Trusted` because of ratings.
-   Ratings do not determine transaction eligibility, price, payment or
    order status.

## 7. Trust Memory

`Verified` means identity/business information was verified.

It does not mean:

-   guaranteed buyer;
-   guaranteed payment;
-   guaranteed price;
-   financially trustworthy.

Use factual information only.

## 8. Transaction Memory

Core lifecycle:

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

After agreement, price, quantity and amount are locked.

## 9. Offline Memory

Offline should be useful, not fake.

Can support:

-   cached information;
-   drafts;
-   safe local records;
-   cached history and receipts.

Must not fake:

-   payment success;
-   fresh market prices;
-   server-confirmed negotiation;
-   face verification;
-   live location;
-   completed transaction state.

Always communicate:

-   current connectivity;
-   last synchronization;
-   pending changes;
-   unavailable actions.

## 10. Design/Code Relationship

`prd.md` = WHAT

`design.md` = HOW IT LOOKS AND BEHAVES

`architecture.md` = HOW FRONTEND CODE IS STRUCTURED

`rules.md` = WHAT IMPLEMENTATION MUST NOT VIOLATE

`tasks.md` = WHAT TO BUILD AND IN WHAT ORDER

`memory.md` = DURABLE PROJECT CONTEXT

## 11. AI Agent Behaviour

When an AI coding/design agent works on MittiMandi:

1.  Read these project documents first.
2.  Do not invent requirements.
3.  Do not silently change product decisions.
4.  Reuse existing components before creating new ones.
5.  Preserve the approved visual identity.
6.  Keep business logic outside UI composables.
7.  Make loading, empty, error and offline states explicit.
8.  Do not present fabricated data as real.
9.  Do not add unsupported languages.
10. Do not introduce green or dark-theme styling.
11. Do not create unsupported rating relationships.
12. Do not turn ratings into trust scores.
13. Ask for clarification when a missing decision materially changes
    product behaviour.
14. Prefer a safe, explicit unknown state over an invented answer.

## 12. Current Priority

The frontend should prioritise the complete farmer selling journey
before polishing secondary modules:

``` text
Authentication
→ Farmer Dashboard
→ Produce/Lot
→ Market
→ Market Comparison
→ Net Realization
→ Buyer Discovery
→ Offer
→ Negotiation
→ Agreement
→ Verification
→ Order
→ Transport
→ Delivery
→ Payment
→ Receipt
→ Rating
```

Secondary role workflows come after the primary transaction path is
stable.
