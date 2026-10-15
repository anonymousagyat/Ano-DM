# 🌐 Ano-DM Companion Chrome Extension

This companion Chrome extension (Manifest V3) automatically intercepts file downloads in Chromium-based browsers (Google Chrome, Microsoft Edge, Brave, Opera) and routes them into **Ano-Download Manager (Ano-DM)** for high-speed multi-interface channel bonding.

---

## 🚀 Installation Instructions

1. Open your browser and navigate to the Extensions page:
   - **Chrome:** `chrome://extensions/`
   - **Edge:** `edge://extensions/`
   - **Brave:** `brave://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click the **Load unpacked** button.
4. Select this directory:
   ```
   D:\Documents\PROJECTS\Ano-Dm-Gui\chrome_extension
   ```
5. The extension icon will appear in your browser toolbar with status **Connected**.

---

## ⚡ How It Works

- Whenever you click a download link or browser download starts:
  1. The extension cancels the default single-threaded browser download.
  2. Sends an HTTP POST request to Ano-DM's local daemon on `http://127.0.0.1:9653/add_download`.
  3. Ano-DM launches the active 32-segment download dialog and bonds your Wi-Fi and 4G/5G mobile connections.
