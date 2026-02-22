# Silver Tracker

Silver Tracker is a privacy-first, client-side web app for tracking silver inventory. The app runs entirely in the browser and is production-ready for static hosting (GitHub Pages, Netlify, or any static host).

## Summary
- Upload, edit and download CSV inventory in the browser.
- Encrypted client-side storage: AES-GCM used for local encrypted blobs (passphrase optional). By default data is stored session-only (sessionStorage); opt-in LocalStorage available.
- Spot price controls: numeric input, slider, and a public quote fetch as a convenience (fetch may be blocked by CORS; manual input works).
- Fully client-side: no server-side persistence unless you export/upload files yourself.

## Production-ready notes
- The app is implemented with React + Vite and styled with MUI for a polished UI.
- A GitHub Actions workflow is included at `.github/workflows/deploy.yml` to build and deploy `dist/` to GitHub Pages on push to `main`.

## Local development
1. Install Node.js (v16+) and npm.
2. Install dependencies and start dev server:

```bash
npm install
npm run dev
```

3. Build production bundle:

```bash
npm run build
```

4. Preview built output locally:

```bash
npm run serve
```

## Preparing for first push to GitHub
1. Initialize and push the repository if you haven't already:

```bash
git init
git add .
git commit -m "Initial Silver Tracker — production-ready"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo>.git
git push -u origin main
```

2. On push, the included GitHub Actions workflow will build and deploy the `dist/` output to the `gh-pages` branch automatically.

## Security & privacy
- Data stays in your browser by default. If you enable persistence, the app will store an encrypted blob in LocalStorage when using a passphrase, or an ephemeral session key otherwise.
- If you use a passphrase, keep it safe — it is required to decrypt stored blobs.
- Do not include PII in CSVs you plan to host publicly.

## Support & next steps
- I can finalize theme tokens, add accessibility improvements, add a passphrase strength meter, or open a PR and push these changes for you.

Would you like me to commit these production-ready changes and push them to a branch now?
