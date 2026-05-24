# Limitations

This is a deliberately conservative tool. Known limits in v1:

- **PDF bibliography extraction is imperfect.** Heavy-typography journals, two-column
  layouts with embedded tables, or scanned PDFs may produce noisy splits. We use
  layered fallbacks (`pymupdf` → `pdfplumber` → `pypdf`) but accuracy varies.
- **OCR is not included in v1.** Image-only PDFs return empty text. A future phase
  may integrate Tesseract or `ocrmypdf` as an opt-in step.
- **References without DOI / arXiv ID / clean title may fail to resolve.** Author
  name disambiguation and cross-language matching are out of scope.
- **Public PDF discovery is best-effort.** Many papers genuinely have no
  open-access copy. The manifest will list these with `reason = "no_oa_pdf_found"`.
- **Some publishers block automated downloads** even of OA-licensed PDFs (via WAF
  rules, JS challenges, etc.). We treat any non-PDF response as failure rather
  than retrying with browser emulation.
- **Institutional access is intentionally NOT scraped.** This tool will never use
  your university VPN, browser cookies, EZproxy, Shibboleth, or any credentialed
  pathway.
- **GROBID / CERMINE / Anystyle** ML reference parsers are not bundled. They can be
  integrated later as optional pre-processors but are not required.
- **Sci-Hub / LibGen and similar mirrors are explicitly denied.** We will not add
  them as configurable options.
- **No browser automation in v1.** No Playwright, Selenium, or headless-Chromium
  fetches. Pure HTTP only.
- **Rate limits are conservative by default.** Heavy use against Crossref/OpenAlex
  may require obtaining your own polite-pool credentials and increasing
  `MAX_CONCURRENT_REQUESTS` after consulting each provider's TOS.
