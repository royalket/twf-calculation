# twf-app

A minimal Vite + React dev app that hosts the `MethodologyFigure` component for local development and export testing.

## Prerequisites

- macOS: a POSIX shell (zsh/bash) is available. Node.js (LTS) and npm are required. `nvm` is recommended to install/manage Node.

## Quick start

Open a terminal and run the following (these commands assume you are in the project root):

```bash
# Install nvm (if you don't have it) and use LTS Node
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.6/install.sh | bash
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install --lts
nvm use --lts

# Change into the app folder, install deps and start dev server
cd twf-app
npm install
npm run dev
```

After the dev server starts, open the app at: http://localhost:5173

## Build & Preview

```bash
# From twf-app/
npm run build
npm run preview
```

The preview server will show the production build (default port printed by the preview command).

## Exporting the figure

- The page includes an "Export PNG" button which uses html2canvas loaded from a CDN to produce a PNG of the figure.
- Note: html2canvas may fail to capture externally hosted images due to CORS. If export fails, the app falls back to copying the figure selection to the clipboard.

## Files

- `src/MethodologyFigure.jsx`: main component containing the figure and toolbar.
- `src/App.jsx`: imports and mounts the component.

## Troubleshooting

- If you see a blank page, open the browser DevTools Console and report any errors here. Common fixes:
  - Ensure Node/npm are installed and you ran `npm install` in `twf-app`
  - If you get build transform errors, check for malformed JSX in `src/MethodologyFigure.jsx`.

## Notes

- This README was added by an assistant to help you run the local dev app and export the figure.
