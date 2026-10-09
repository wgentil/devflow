# End-of-build site update offer

After DevFlow records an authorized delivery result or a ready-to-merge PR,
report the result and ask once:

> The build is complete. Would you like me to update the
> [DevFlow Codex site](https://devflow-field-guide.waygent.chatgpt.site/)
> with this build?

If the user says no or does not answer, the build remains delivered. If the user
says yes, treat the site update as a separate task. The prompt alone does not
change or publish the site. A failed or blocked build does not trigger the offer.
