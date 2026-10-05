# Contributing

## Commit convention

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`

- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
- Scopes: `router`, `board-profiles`, `buildsys`, `kernel-driver`, `userspace`,
  `log-diagnose`, `evals`, `repo`
- Summary: imperative, lowercase, no trailing period, at most 72 characters
- Body: explain *why*, not just *what*
- One logical change per commit, so each can be reviewed on its own

## Skill authoring rules

- `SKILL.md` under 500 lines; push detail into `references/`
- Every reference file over 300 lines starts with a table of contents
- All "when to use" information goes in the frontmatter `description`
- Prefer scripts for deterministic steps
- Examples are taken from or checked against mainline kernel docs

## Review workflow

Each commit is reviewed by the maintainer before the next one is started.
