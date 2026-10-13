# Example UX review report

This illustrates report structure; it is not an observation of a real product.

**Task:** A first-time mobile customer completes checkout.

**Evidence inspected:** A supplied screenshot of the shipping form and draft
checkout requirements. No live interface was available.

| Priority | Type and location | Evidence and impact | Recommendation and check |
| --- | --- | --- | --- |
| Medium | Observed visible defect — shipping form, phone field | The screenshot shows a field with no visible label. A customer may not know which number to enter. The screenshot cannot establish its accessible name. | Add a persistent visible label. Inspect the live form and check the field's accessible name with a screen reader. |
| Medium | Requirement gap — checkout specification, payment errors | The draft requirements describe successful payment but give no acceptance criterion for a declined card. A customer may be unable to understand or recover from a failure; no implementation defect has been observed. | Define the error message, retained form state, and retry path, then test the live decline flow. |

**Coverage and open checks:** The screenshot supports visible layout and copy
observations only. Loading, errors, keyboard use, screen-reader output, and
successful checkout were not tested. A staging checkout and safe test payment
method are needed to verify those behaviors.
