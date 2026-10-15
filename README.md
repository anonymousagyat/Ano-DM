# ⚡ Ano-Download Manager (Ano-DM)

<p align="center">
  <img src="assets/icon.png" width="100" height="100" alt="Ano-DM Logo" />
</p>

<p align="center">
  <strong>High-Speed Multi-Interface Channel Bonding Download Accelerator for Windows</strong>
  <br />
  <em>Aggregates Home Wi-Fi + Mobile 4G/5G USB Tethering to double download speeds (e.g. 5 MB/s + 5 MB/s = 10 MB/s).</em>
  <br />
  <em>Includes both a modern <strong>Desktop GUI</strong> and a powerful <strong>Terminal CLI</strong> in a single repository.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat&logo=windows&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/UI-CustomTkinter-7C3AED?style=flat" alt="CustomTkinter" />
  <img src="https://img.shields.io/badge/CLI-Rich%20Terminal-00F5D4?style=flat" alt="Rich Terminal" />
  <img src="https://img.shields.io/badge/Extension-Chrome%20MV3-4285F4?style=flat&logo=googlechrome&logoColor=white" alt="Chrome MV3" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="License" />
</p>

---

## 📖 Overview

Most standard download managers and browsers route all traffic through your PC's primary default network adapter (usually Wi-Fi). If your home Wi-Fi plan is capped at 5 MB/s, opening multiple downloads only divides that 5 MB/s between files.

**Ano-Download Manager (Ano-DM)** bypasses this limit using socket-level adapter binding (`source_address=(interface_ip, 0)`). By simultaneously connecting your PC to your **Home Wi-Fi** and your smartphone via **USB Tethering (4G/5G Mobile Data)**, Ano-DM splits downloads into concurrent byte chunks and pulls data across **both independent network adapters at the same time**—achieving combined aggregate speeds without requiring any paid cloud VPS or third-party bonding VPN.

```
                              ┌── Socket Pool A ──► Wi-Fi (5 MB/s)       ──┐
[Ano-DM Multi-Interface Engine]                                            ├──► [Remote Server]
                              └── Socket Pool B ──► USB Tethering (5 MB/s)──┘
                                                    Total: ~10 MB/s Combined Speed
```

---

## ✨ Features

* 🖥️ **Flagship Desktop GUI:**
  * Clean dark-purple Neat Download Manager (NDM 1.4) dashboard layout.
  * In-place tabs: `[ Download ]`, `[ Options ]` (bandwidth limiter), `[ Connections ]` (stream counter).
  * 32-segment 3D glass LED gradient visualizer with specular highlights.
  * Windows Shell integration: displays genuine default application icons (e.g. **WinRAR for `.rar`**, 7-Zip for `.zip`, VLC for `.mp4`).
  * System tray daemon (hidden icons near clock) with quick actions (`Open Main Window`, `New Download`, `Exit`).
  * Embedded HTTP listener (`127.0.0.1:9653`) communicating with browser extensions.
* 💻 **Powerful Terminal CLI:**
  * Rich live terminal tables with per-adapter throughput meters and aggregate speed graphs.
  * ASCII stream block map (`█ Done | ▒ Active | ░ Queued`).
  * Interactive wizard or scriptable one-liners for terminal/headless usage.
* ⚡ **Shared Core Engine:**
  * Dynamic range-based chunk allocation with work-stealing across adapters.
  * Lock-free `.part` segment downloads with instant zero-latency resume.
  * Safe Pause & Cancel (purges temporary `.part` files immediately on cancel).

---

## 📂 Project Structure

```
Ano-DM/
├── assets/                     # High-DPI logos, Windows app icon, archive graphic
│   ├── icon.ico                # Multi-resolution icon (256 down to 16)
│   ├── icon.png                # High-DPI application logo
│   ├── user_logo.png           # Original master logo
│   └── file_archive.png        # 3D metallic archive graphic
├── chrome_extension/           # Manifest V3 browser companion
│   ├── manifest.json           # Extension manifest (MV3)
│   ├── background.js           # Download interceptor service worker
│   ├── icon16.png, icon48.png, icon128.png
│   └── README.md               # Extension installation guide
├── downloads/                  # Default download directory (tracked via .gitkeep)
│   └── temp/                   # Temporary .part chunk directory
├── scripts/                    # Automation & build scripts
│   └── build.py                # Standalone PyInstaller packaging script
├── ano_dm.py                   # Flagship Desktop GUI & Daemon (Default entry)
├── cli.py                      # Terminal CLI with Rich ASCII telemetry & CLI args
├── engine.py                   # Core dual-bond download engine (Shared)
├── network_scanner.py          # Network adapter scanner & validator (Shared)
├── part_manager.py             # Segment part manager & merger (Shared)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
├── LICENSE                     # MIT License
└── README.md                   # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
* **Windows 10 or 11 (64-bit)**
* **Python 3.10+** (if running from source)
* Two active network connections connected simultaneously:
  1. Primary Wi-Fi connection
  2. Mobile Data via USB Tethering (Turn OFF phone Wi-Fi, turn ON Mobile Data, enable USB Tethering in phone settings)

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/anonymousagyat/Ano-DM.git
cd Ano-DM

# Install dependencies
pip install -r requirements.txt
```

---

## 🖥️ Running the Desktop GUI (Default)

Launch the flagship GUI application with:

```powershell
python ano_dm.py
```

* **What it does:** Opens the NDM Main Dashboard Window and starts the background tray daemon.
* **Chrome Integration:** Any download initiated in your browser automatically opens the active 32-segment download dialog.
* **Closing the Window:** Minimizes cleanly into your Windows hidden tray icons near the clock. Right-click the tray icon to select **Open Main Window** or **Exit**.

---

## 💻 Running the Terminal CLI Mode

If you prefer using the terminal, are over an SSH session, or want to write batch scripts, Ano-DM provides a full-featured CLI:

### 1. Interactive CLI Wizard
```powershell
python cli.py
```
* Automatically scans and displays all detected network adapters.
* Prompts you to pick which adapters to bond.
* Prompts for stream count (8, 16, 32 connections) and download URL.

### 2. Direct One-Liner Download
Pass the download URL directly on the command line:

```powershell
python cli.py "https://example.com/file.zip"
```

### 3. Advanced CLI Options
```powershell
# Download with 32 streams and auto-bond all online adapters without prompting
python cli.py "https://example.com/file.zip" -s 32 -a

# Specify a custom destination path
python cli.py "https://example.com/file.zip" -o "D:\Downloads\MyFile.zip"
```

### 4. Running CLI via the Main Entrypoint
You can also launch CLI mode using the main `ano_dm.py` file:
```powershell
python ano_dm.py --cli "https://example.com/file.zip"
```

---

## 🌐 Chrome Extension Setup

1. Open **Google Chrome** (or Edge/Brave) and navigate to `chrome://extensions/`.
2. Toggle on **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the `chrome_extension/` directory.
4. With Ano-DM running, any browser download is automatically caught and accelerated!

---

## 🔨 Packaging into a Standalone Executable (.exe)

Compile the application into a standalone Windows `.exe` that requires no Python installation:

```powershell
python scripts/build.py
```

The compiled binary will be placed at:
```
dist/Ano-DM/Ano-DM.exe
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
