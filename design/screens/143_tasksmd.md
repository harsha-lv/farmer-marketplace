# MittiMandi --- Frontend Implementation Tasks

## 0. Working Rule

Implement in dependency order.

Do not build every screen independently first. Build the foundation,
then shared components, then authentication, then the core farmer
transaction journey, then supporting roles.

Status:

-   `[ ]` Not started
-   `[~]` In progress
-   `[x]` Complete
-   `[!]` Blocked

------------------------------------------------------------------------

## 1. Project Foundation

-   [ ] Create Android Kotlin project.
-   [ ] Configure Jetpack Compose.
-   [ ] Configure Material 3.
-   [ ] Configure navigation.
-   [ ] Configure build variants/environment configuration.
-   [ ] Establish package structure.
-   [ ] Add lint/static analysis.
-   [ ] Add unit-test infrastructure.
-   [ ] Add Compose UI test infrastructure.
-   [ ] Add repository/domain/data layers.

## 2. Design System

-   [ ] Create central colour tokens from `design.md`.
-   [ ] Implement light theme only.
-   [ ] Remove green from brand/status palette.
-   [ ] Implement Sky Blue.
-   [ ] Implement Burnt Orange.
-   [ ] Implement Market Amber.
-   [ ] Implement warm light neutrals.
-   [ ] Implement typography.
-   [ ] Implement spacing scale.
-   [ ] Implement shape/radius tokens.
-   [ ] Implement elevation rules.
-   [ ] Implement button variants.
-   [ ] Implement input variants.
-   [ ] Implement cards.
-   [ ] Implement status chips.
-   [ ] Implement icons and icon rules.
-   [ ] Implement accessibility semantics.

## 3. Localization

-   [ ] Create string resources.
-   [ ] Add English.
-   [ ] Add Hindi.
-   [ ] Add Marathi.
-   [ ] Add Kannada.
-   [ ] Add Telugu.
-   [ ] Add Tamil.
-   [ ] Test text expansion.
-   [ ] Test 200% font scale.
-   [ ] Verify no hard-coded user-facing strings.

## 4. Core App Infrastructure

-   [ ] Create app navigation shell.
-   [ ] Implement session manager.
-   [ ] Implement connectivity observer.
-   [ ] Implement offline banner.
-   [ ] Implement sync status.
-   [ ] Implement global error handling.
-   [ ] Implement permission handling.
-   [ ] Implement loading/empty/error components.
-   [ ] Implement freshness indicator.
-   [ ] Implement notification infrastructure.

## 5. Authentication

-   [ ] Splash.
-   [ ] Language selection.
-   [ ] Login.
-   [ ] OTP.
-   [ ] Role selection.
-   [ ] Farmer registration.
-   [ ] Buyer registration.
-   [ ] FPO registration.
-   [ ] Transport registration.
-   [ ] Storage registration.
-   [ ] Session expiry.
-   [ ] Unauthorized handling.

## 6. Farmer Foundation

-   [ ] Farmer dashboard.
-   [ ] Farmer profile.
-   [ ] Farm details.
-   [ ] My crops.
-   [ ] Add produce.
-   [ ] Produce details.
-   [ ] Lot creation.
-   [ ] Mandatory sample photo.
-   [ ] Mandatory full-lot photo.
-   [ ] Optional video.
-   [ ] Offline draft saving.
-   [ ] Lot validation.

## 7. Market Intelligence

-   [ ] Market dashboard.
-   [ ] Current prices.
-   [ ] Market comparison.
-   [ ] Market history.
-   [ ] Trend display.
-   [ ] Forecast display.
-   [ ] Forecast disclaimer.
-   [ ] Source/freshness display.
-   [ ] Market opportunity card.
-   [ ] Price alerts.
-   [ ] Demand alerts.
-   [ ] Market Signal component.
-   [ ] Market Compass component.
-   [ ] Money Path component.
-   [ ] Decision Strip component.
-   [ ] Cost Waterfall / net-realization presentation.

## 8. Buyer Discovery

-   [ ] Buyer discovery.
-   [ ] Buyer filters.
-   [ ] Buyer profile.
-   [ ] Buyer requirements.
-   [ ] Verification display.
-   [ ] Factual reliability information.
-   [ ] Rating summary.
-   [ ] Recent reviews.
-   [ ] `No ratings yet` state.

## 9. Offers and Negotiation

-   [ ] Send offer.
-   [ ] Offer detail.
-   [ ] Counter offer.
-   [ ] Negotiation state.
-   [ ] Agreement state.
-   [ ] Open-to-negotiation rule.
-   [ ] Price lock.
-   [ ] Quantity lock.
-   [ ] Amount lock.
-   [ ] Locked-value presentation.
-   [ ] Contact reveal according to product rule.

## 10. Face Verification

-   [ ] Permission state.
-   [ ] Camera state.
-   [ ] Position guidance.
-   [ ] Capture.
-   [ ] Processing.
-   [ ] Success.
-   [ ] Failure.
-   [ ] Retry.
-   [ ] Network failure.
-   [ ] No face-match score in UI.

## 11. Orders and Transactions

-   [ ] Order creation.
-   [ ] Order details.
-   [ ] Transaction timeline.
-   [ ] Transaction state machine.
-   [ ] Transport selection.
-   [ ] Storage selection.
-   [ ] Delivery state.
-   [ ] Payment state.
-   [ ] Receipt.
-   [ ] Transaction history.
-   [ ] Filters.
-   [ ] Report transaction.

## 12. Transport

-   [ ] Transport provider profile.
-   [ ] Vehicle management.
-   [ ] Requests.
-   [ ] Accept request.
-   [ ] Delivery workflow.
-   [ ] Navigation/tracking state.
-   [ ] Pickup state.
-   [ ] Loading state.
-   [ ] Transit state.
-   [ ] Reached buyer.
-   [ ] Delivered.
-   [ ] Last-known-location state.
-   [ ] Transport rating.

## 13. Storage

-   [ ] Storage provider profile.
-   [ ] Storage facility.
-   [ ] Capacity.
-   [ ] Crop suitability.
-   [ ] Availability.
-   [ ] Cost.
-   [ ] Storage request.
-   [ ] Active storage.
-   [ ] Storage completion.
-   [ ] Storage payment.

## 14. Payments

-   [ ] Payment screen.
-   [ ] Bank transfer state.
-   [ ] UPI/online payment state.
-   [ ] Pending.
-   [ ] Processing.
-   [ ] Successful.
-   [ ] Failed.
-   [ ] Unknown/error handling.
-   [ ] Receipt integration.

## 15. Ratings

-   [ ] RatingSummary.
-   [ ] RatingInput.
-   [ ] RatingCard.
-   [ ] RateAction.
-   [ ] Farmer → Buyer rating.
-   [ ] Farmer → Transport rating.
-   [ ] Buyer → Transport rating.
-   [ ] Block Buyer → Farmer rating.
-   [ ] Completed-transaction eligibility.
-   [ ] Duplicate-rating prevention.
-   [ ] No-ratings state.
-   [ ] Submitted state.
-   [ ] Submission failure.
-   [ ] Pending submission.
-   [ ] Review moderation/reporting.

## 16. FPO

-   [ ] FPO dashboard.
-   [ ] Farmer management.
-   [ ] Aggregated lots.
-   [ ] Market view.
-   [ ] Buyer discovery.
-   [ ] Offers.
-   [ ] Logistics.
-   [ ] Storage.
-   [ ] Transactions.
-   [ ] FPO profile.

## 17. Buyer

-   [ ] Buyer dashboard.
-   [ ] Requirements.
-   [ ] Lot discovery.
-   [ ] Offers.
-   [ ] Negotiation.
-   [ ] Orders.
-   [ ] Delivery.
-   [ ] Payments.
-   [ ] Transactions.
-   [ ] Transport rating.

## 18. Admin

-   [ ] Admin authentication.
-   [ ] Admin dashboard.
-   [ ] User verification.
-   [ ] Transaction monitoring.
-   [ ] Payment monitoring.
-   [ ] Offer monitoring.
-   [ ] Suspicious activity.
-   [ ] Grievances.
-   [ ] Reports.
-   [ ] Protected navigation.

## 19. Offline and Sync

-   [ ] Local cache.
-   [ ] Cached market data.
-   [ ] Draft lot storage.
-   [ ] Cached transaction history.
-   [ ] Cached receipts.
-   [ ] Pending-operation queue only for safe supported operations.
-   [ ] Sync worker.
-   [ ] Retry.
-   [ ] Conflict handling.
-   [ ] Server-authoritative locked data protection.
-   [ ] Data Saver mode.

## 20. Accessibility

-   [ ] 48 dp touch targets.
-   [ ] Content descriptions.
-   [ ] TalkBack testing.
-   [ ] 200% font scale.
-   [ ] 320 dp width.
-   [ ] Focus order.
-   [ ] Contrast.
-   [ ] Non-colour status communication.
-   [ ] Screen-reader chart alternatives.

## 21. Testing

-   [ ] Authentication unit tests.
-   [ ] Market formatter tests.
-   [ ] Net realization tests.
-   [ ] Transaction state tests.
-   [ ] Rating eligibility tests.
-   [ ] Duplicate rating tests.
-   [ ] Payment state tests.
-   [ ] Offline state tests.
-   [ ] Sync tests.
-   [ ] Navigation tests.
-   [ ] Compose screen tests.
-   [ ] Localization tests.
-   [ ] Accessibility tests.

## 22. Final QA

-   [ ] No green brand elements.
-   [ ] No dark theme.
-   [ ] No black-heavy cards.
-   [ ] No fake data presented as real.
-   [ ] No fake ratings.
-   [ ] No fake forecasts.
-   [ ] No fake live location.
-   [ ] No accidental editable locked values.
-   [ ] No unsupported language.
-   [ ] No broken offline states.
-   [ ] No hard-coded UI strings.
-   [ ] No missing loading/empty/error states.
-   [ ] No unnecessary duplicate components.
-   [ ] PRD/design/architecture/rules remain consistent.

## 23. Stitch Handoff Order

When using Stitch for visual generation, generate screens in this order:

1.  Splash / Language
2.  Login / OTP
3.  Role selection
4.  Farmer dashboard
5.  Market dashboard
6.  Market comparison
7.  Net realization / decision screen
8.  Buyer discovery
9.  Buyer profile
10. Offer / negotiation
11. Agreement / locked transaction
12. Face verification
13. Order details
14. Transport / delivery
15. Payment / receipt
16. Transaction history
17. Rating
18. FPO screens
19. Buyer screens
20. Transport screens
21. Storage screens
22. Admin screens

The Stitch output must follow `design.md`; it must not create a
different visual language for individual screens.
