# DevFlow repository instructions

## Keep documentation current

Whenever DevFlow is updated, update the affected documentation in the same change.
Documentation is part of completion, not a separate follow-up task.

- For skill changes, update its `SKILL.md`, companion `GUIDE.md`, and Mermaid
  diagram wherever the instructions, usage, or process changes.
- For command, input, output, or workflow changes, update the relevant guides,
  shared references in `docs/`, and example files in `docs/examples/`.
- Treat `docs/setup-and-usage.md` as the primary setup and usage guide. Review it
  after every DevFlow change and update initialization, setup, workflow, host,
  upgrade and troubleshooting instructions whenever affected.
- Keep `docs/skills.md` current when skills or documentation locations change.
- Describe actual implemented behavior, including limitations and required human
  or external actions. Do not document intended behavior as already implemented.
- Before completing the change, check affected links, examples, command syntax,
  and skill metadata. Exercise runnable examples when their behavior changes.

If a change does not affect documented behavior, review the relevant documentation
and state that no content update was needed in the completion report.
