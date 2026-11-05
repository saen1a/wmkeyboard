# Task: docs page

## Page

- Path: `docs/src/content/docs/<section>/<page>.mdx`
- Audience: <user, power user, or developer>
- Job: <the one question the page answers>

## Evidence

List the code paths that prove each claim. A page written from memory is a list
of hypotheses.

- <behaviour> -> `path/to/File.kt:line`
- <setting> -> `path/to/Settings.kt:line`

## Rules

- Read `docs/CONTENT_GUIDE.md` first.
- Keep the frontmatter `description`, quoted.
- Absolute links with a trailing slash.
- No stub ships without `:::caution[Draft page]`.
- Privacy claims name what is sent, to whom, and when.

## Verification

```sh
cd docs && npm ci && npm run check
```

## Halt

Stop when a claim cannot be verified from the code and no device check is
available. Mark it `Cannot verify` instead of writing a plausible sentence.

## Handoff

Hand the page, the evidence list, and the build output to `review-lead`.
