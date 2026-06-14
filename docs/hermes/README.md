# Hermes Durable Artifacts

This directory stores durable, reviewable Hermes collaboration templates for
this repository.

Use `docs/hermes/` for:

- reusable DeepSeek coding brief templates
- reusable Codex review packet templates
- stable Hermes workflow notes that should be versioned with the repo

Do not use `docs/hermes/` for:

- current run status
- transient blocker files
- timestamped run logs
- branch-local execution outputs

Those runtime artifacts remain under `.hermes/`, which is intentionally kept
out of Git because it is local execution state rather than durable project
documentation.

Current durable templates:

- [DeepSeek Brief Template](./deepseek_brief_template.md)
- [Codex Review Packet Template](./codex_review_packet_template.md)
