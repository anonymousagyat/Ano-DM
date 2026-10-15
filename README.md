# ⚡ Ano-Download Manager (Ano-DM)

<p align="center">
  <img src="assets/icon.png" width="100" height="100" alt="Ano-DM Logo" />
</p>

<p align="center">
  <strong>High-Speed Multi-Interface Channel Bonding Download Accelerator for Windows</strong>
  <br />
  <em>Aggregates Home Wi-Fi + Mobile 4G/5G USB Tethering to double download speeds (e.g. 5 MB/s + 5 MB/s = 10 MB/s).</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat&logo=windows&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/UI-CustomTkinter-7C3AED?style=flat" alt="CustomTkinter" />
  <img src="https://img.shields.io/badge/Extension-Chrome%20MV3-4285F4?style=flat&logo=googlechrome&logoColor=white" alt="Chrome MV3" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat" alt="License" />
</p>

---

## 📖 Overview

Most standard download managers and web browsers route all outbound network traffic through your primary default gateway (usually your home Wi-Fi). If your Wi-Fi plan is capped at 5 MB/s, opening multiple downloads only splits that 5 MB/s between files.

**Ano-Download Manager (Ano-DM)** breaks past this bottleneck by using low-level socket-binding (`source_address=(interface_ip, 0)`). By simultaneously connecting your PC to your **Home Wi-Fi** and your smartphone via **USB Tethering (Mobile 4G/5G)**, Ano-DM splits file downloads into concurrent segments and pulls data across **both independent physical network interfaces at the same time**—without requiring an expensive cloud VPS or third-party VPN subscription.

```
                              ┌── Socket Pool A ──► Wi-Fi (5 MB/s)       ──┐
[Ano-DM Multi-Interface Engine]                                            ├──► [File Server]
                              └── Socket Pool B ──► USB Tethering (5 MB/s)──┘
                                                    Total: ~10 MB/s Aggregated Speed
```

---

## ✨ Features

* **Neat Download Manager (NDM 1.4) Design:** Clean, dark purple desktop dashboard with toolbar, category sidebar, and framed tabs.
* **Dual-Interface Channel Bonding:** Automatically discovers active network adapters, validates internet connectivity, and balances chunks across adapters.
* **32-Segment Gradient Visualizer:** 3D glass LED indicator slots showing real-time downloaded, active, and queued segments with top specular sheen.
* **Windows Shell Default App Icons:** Dynamically queries the Windows Shell (`SHGetFileInfo`) to display the genuine default application icon (e.g., WinRAR for `.rar`, 7-Zip for `.zip`, VLC for `.mp4`).
* **Companion Chrome Extension (Manifest V3):** Automatically catches downloads from Google Chrome, Edge, and Brave and redirects them to Ano-DM.
* **Lightweight & System Tray Integration:** Minimizes cleanly into the Windows hidden tray icons near the clock.
* **Rock-Solid Pause & Cancel:** 
  * **Pause:** Stops worker sockets without triggering premature file completion or corruption.
  * **Cancel:** Purges all temporary `.part` files immediately from disk.
* **Persistent History:** Automatically persists download status in `downloads/history.json`.

---

## 📂 Project Structure

```
Ano-Dm-Gui/
├── assets/
│   ├── icon.ico              # Multi-resolution application icon
│   ├── icon.png              # High-DPI application branding logo
│   ├── user_logo.png         # High-resolution master logo
│   └── file_archive.png      # High-res fallback archive graphic
├── chrome_extension/
│   ├── manifest.json         # Manifest V3 extension configuration
│   ├── background.js         # Download interception service worker
│   ├── icon16.png            # 16x16 extension icon
│   ├── icon48.png            # 48x48 extension icon
│   ├── icon128.png           # 128x128 extension icon
│   └── README.md             # Extension loading instructions
├── downloads/                # Default save folder for downloaded files
│   └── temp/                 # Temporary chunk files (.part0, .part1, ...)
├── scripts/
│   └── build.py              # Automated PyInstaller packaging script
├── ano_dm.py                 # Main Application GUI & Daemon
├── engine.py                 # Multi-adapter socket engine & chunk workers
├── network_scanner.py        # Windows adapter detection & connectivity tester
├── part_manager.py           # Lock-free .part manager & sequential merger
├── requirements.txt          # Python dependencies
├── .gitignore                # Git ignore rules
├── LICENSE                   # MIT License
└── README.md                 # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
* **Windows 10 or 11 (64-bit)**
* **Python 3.10+** (if running from source)
* Two independent network connections connected simultaneously:
  1. Primary Wi-Fi connection
  2. Mobile Data via USB Tethering (Turn OFF phone Wi-Fi, turn ON Mobile Data, enable USB Tethering in phone settings)

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/your-username/Ano-DM.git
cd Ano-DM

# Install dependencies
pip install -r requirements.txt
```

### 3. Launching the Application
```powershell
# Run GUI application
python ano_dm.py
```

---

## 🌐 Chrome Extension Setup

1. Open **Google Chrome** (or Edge/Brave) and navigate to `chrome://extensions/`.
2. Toggle on **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the `chrome_extension/` folder in this repository.
4. When Ano-DM is running in your system tray, any download started in your browser will automatically launch in Ano-DM!

---

## 🔨 Packaging into a Standalone Executable (.exe)

You can compile Ano-DM into a standalone `.exe` that requires no Python installation:

```powershell
python scripts/build.py
```

The compiled executable will be generated at:
```
dist/Ano-DM/Ano-DM.exe
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
