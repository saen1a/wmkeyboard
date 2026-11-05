---
name: convert-documents-to-markdown
description: Convert Word (.doc, .docx), PowerPoint (.ppt, .pptx), Excel (.xls, .xlsx), OpenDocument (.odt, .ods, .odp), RTF, EPUB, CSV, and PDF files to GitHub-Flavored Markdown. Use when a task needs the contents of an office document, spreadsheet, presentation, ebook, or PDF you cannot read directly.
license: MIT
metadata:
  author: firecrawl
---
<!-- Archetype copy imported from containeromat stacks/deepseek-harness/config/skills/convert-documents-to-markdown (pinned 2026-09-19). Canon switch deferred; see PLAN.md wave 2. -->

# Convert documents to Markdown

Run the anydoc CLI. It needs Node 20+ and no install:

```bash
npx -y @firecrawl/anydoc <file>              # Markdown to stdout
npx -y @firecrawl/anydoc <file> -o out.md    # write to a file
npx -y @firecrawl/anydoc - --format csv < f  # read stdin
```

Rules:

1. Supported inputs: `.doc`, `.docx`, `.docm`, `.odt`, `.rtf`, `.epub`, `.pdf`, `.ppt`, `.pps`, `.pot`, `.pptx`, `.pptm`, `.ppsx`, `.ppsm`, `.odp`, `.xls`, `.xlsx`, `.xlsm`, `.xlsb`, `.ods`, `.csv`.
2. The format is detected from the file content. Pass `--format <name>` only when detection cannot work: CSV from stdin, or a missing or wrong extension.
3. Exit codes: 0 success, 1 the document could not be read or converted, 2 usage error, 3 the PDF pages need OCR. Failures print one `anydoc: <message>` line to stderr. The CLI never prompts.
4. For a large document, write to a file with `-o` and read the parts you need instead of streaming everything into context.
5. Scanned and image-only PDFs need OCR. Default behavior rejects them with exit 3; rerun with `--ocr hosted` to send the document to Firecrawl Parse (API key via `--api-key` or `FIRECRAWL_API_KEY`). If no key or network is available, stop and report; do not attempt local OCR.
6. Inside a Node, Python, or Rust codebase, prefer the library over shelling out: `@firecrawl/anydoc` on npm, `firecrawl-anydoc` on PyPI, `anydoc` on crates.io. Each exposes the same `to_markdown` / `toMarkdown` API.

## Output contract

- Report line: converted file(s) and the exit code.
- Artifact convention: prefer stdout; on a read-only mount write to /tmp.
- Failure line: name the failed input and stop.

## Doctrine position

Serves Implement and Verify for document conversion only: produce the Markdown and confirm it is faithful and clean. Outputs feed Plan and Review consumers; Push stays with the operator.
