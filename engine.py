"""
NDM-Style Dual-Bond Multi-Interface Download Accelerator Engine
Combines:
  1. Multi-interface socket binding (Wi-Fi + USB Tethering).
  2. NDM-style lock-free temporary part files (.part0, .part1, ...).
  3. High-throughput 256KB socket streaming buffers.
  4. True pause & resume based on existing .part byte sizes.
  5. Fast sequential binary assembly.
"""

import os
import re
import time
import queue
import threading
import urllib.parse
from typing import List, Dict, Callable, Optional, Tuple
import urllib3
import requests

from part_manager import SegmentPartManager, SegmentPart

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def sanitize_filename(filename: str) -> str:
    """Removes characters forbidden on Windows file systems."""
    cleaned = re.sub(r'[\\/*?:"<>|\r\n\t]', '_', filename)
    cleaned = cleaned.strip('. ')
    return cleaned or "downloaded_file"


def extract_filename_from_headers(headers: dict, url: str) -> str:
    """Parses Content-Disposition accurately according to RFC 6266 / RFC 5987."""
    cd = headers.get("Content-Disposition", "")
    if cd:
        match_star = re.search(r"filename\*\s*=\s*(?:UTF-8''|utf-8'')?([^;]+)", cd, re.IGNORECASE)
        if match_star:
            raw = match_star.group(1).strip('"\' ')
            try:
                decoded = urllib.parse.unquote(raw)
                return sanitize_filename(decoded)
            except Exception:
                return sanitize_filename(raw)

        match = re.search(r'filename\s*=\s*("([^"]+)"|([^;]+))', cd, re.IGNORECASE)
        if match:
            raw = match.group(2) if match.group(2) is not None else match.group(3)
            return sanitize_filename(raw.strip('"\' '))

    parsed = urllib.parse.urlparse(url)
    base = os.path.basename(parsed.path)
    if base and base != "__down":
        try:
            return sanitize_filename(urllib.parse.unquote(base))
        except Exception:
            return sanitize_filename(base)

    return "downloaded_file.bin"


class AdapterWorker:
    """Manages outgoing connection pool bound strictly to a physical network interface IP."""
    def __init__(self, interface_name: str, interface_ip: str, max_streams: int = 16, timeout: float = 20.0):
        self.name = interface_name
        self.ip = interface_ip
        self.pool = urllib3.PoolManager(
            source_address=(interface_ip, 0),
            timeout=urllib3.Timeout(connect=10.0, read=timeout),
            maxsize=max_streams + 4,
            cert_reqs='CERT_NONE'
        )
        self.total_bytes = 0
        self.current_speed_bps = 0.0
        self._recent_bytes = 0
        self._last_speed_time = time.time()
        self._lock = threading.Lock()
        self.status = "Ready"
        self.consecutive_errors = 0
        self.is_disabled = False
        self._ema_alpha = 0.35  # Smoothing factor (NDM-style gradual transitions)

    def record_bytes(self, byte_count: int):
        with self._lock:
            self.total_bytes += byte_count
            self._recent_bytes += byte_count

    def update_speed(self) -> float:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_speed_time
            if elapsed >= 0.1:  # Sample every 100ms for high-frequency real-time updates
                instant_speed = self._recent_bytes / elapsed
                if self.current_speed_bps == 0.0:
                    self.current_speed_bps = instant_speed
                else:
                    # Exponential Moving Average: smooths out bursty packet deliveries
                    self.current_speed_bps = (self._ema_alpha * instant_speed) + ((1.0 - self._ema_alpha) * self.current_speed_bps)
                
                self._recent_bytes = 0
                self._last_speed_time = now
            return self.current_speed_bps


class DualBondDownloader:
    """
    NDM-Style multi-stream download coordinator with adapter bonding.
    """
    def __init__(
        self,
        url: str,
        output_path: str = "",
        interfaces: Optional[List[Dict[str, str]]] = None,
        num_connections: int = 16,
        temp_dir: Optional[str] = None
    ):
        self.url = url
        self.output_path = output_path
        self.num_connections = max(1, num_connections)
        
        # Temp directory for .part files
        if not temp_dir:
            base_dir = os.path.dirname(os.path.abspath(output_path)) if output_path else os.getcwd()
            temp_dir = os.path.join(base_dir, "temp")
        self.temp_dir = temp_dir
        
        self.file_size = 0
        self.accepts_ranges = False
        self.suggested_filename = ""
        
        # Setup adapter workers
        self.interfaces = interfaces or []
        self.workers: Dict[str, AdapterWorker] = {}
        streams_per_adapter = max(2, self.num_connections // max(1, len(self.interfaces)))
        for iface in self.interfaces:
            ip = iface["ip"]
            name = iface["name"]
            self.workers[ip] = AdapterWorker(name, ip, max_streams=streams_per_adapter)

        self.part_manager: Optional[SegmentPartManager] = None
        self.part_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self.is_merging = False
        self.has_error = False
        self.error_message = ""
        self.merge_progress = 0.0

    def probe_file(self) -> Tuple[int, bool, str]:
        """Queries target URL for size, ranges, and clean filename."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }

        content_length = 0
        accept_ranges = False
        filename = ""

        try:
            probe_headers = dict(headers)
            probe_headers["Range"] = "bytes=0-0"
            resp = requests.get(
                self.url,
                headers=probe_headers,
                stream=True,
                timeout=(10.0, 15.0),
                verify=False,
                allow_redirects=True
            )

            if resp.status_code == 206:
                accept_ranges = True
                content_range = resp.headers.get("Content-Range", "")
                if "/" in content_range:
                    try:
                        content_length = int(content_range.split("/")[-1].strip())
                    except ValueError:
                        pass
            elif resp.status_code == 200:
                accept_ranges = False
                content_length = int(resp.headers.get("Content-Length", 0))

            filename = extract_filename_from_headers(resp.headers, self.url)
            resp.close()
        except Exception:
            try:
                resp = requests.head(
                    self.url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=(10.0, 15.0),
                    verify=False
                )
                content_length = int(resp.headers.get("Content-Length", 0))
                accept_ranges = resp.headers.get("Accept-Ranges", "").lower() == "bytes"
                filename = extract_filename_from_headers(resp.headers, self.url)
            except Exception as e:
                raise RuntimeError(f"Could not reach server: {e}")

        self.file_size = content_length
        self.accepts_ranges = accept_ranges
        self.suggested_filename = filename
        return content_length, accept_ranges, filename

    def _worker_stream(self, worker: AdapterWorker):
        """Dedicated thread executing NDM-style lock-free downloads directly to part files."""
        buffer_size = 32 * 1024  # 32 KB slices for rapid, low-latency telemetry updates

        while self.is_running:
            if worker.is_disabled:
                break

            try:
                part: SegmentPart = self.part_queue.get(timeout=0.5)
            except queue.Empty:
                break

            if part.is_complete:
                self.part_queue.task_done()
                continue

            part.assigned_adapter = worker.name
            part.status = "Downloading"
            worker.status = "Active"

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Range": f"bytes={part.current_start}-{part.orig_end}",
                    "Accept": "*/*"
                }

                resp = worker.pool.request("GET", self.url, headers=headers, preload_content=False)

                if resp.status not in (200, 206):
                    raise IOError(f"HTTP {resp.status}")

                worker.consecutive_errors = 0

                # Lock-free append to dedicated part file
                with open(part.path, "ab") as f:
                    for chunk in resp.stream(buffer_size):
                        if not self.is_running:
                            break
                        f.write(chunk)
                        chunk_len = len(chunk)
                        part.downloaded_bytes += chunk_len
                        part.current_start += chunk_len
                        worker.record_bytes(chunk_len)

                resp.release_conn()

                if part.downloaded_bytes >= part.total_size:
                    part.is_complete = True
                    part.status = "Completed"

            except Exception as e:
                worker.consecutive_errors += 1
                part.status = f"Retrying"
                worker.status = f"Err ({e.__class__.__name__})"

                if worker.consecutive_errors >= 4:
                    worker.is_disabled = True
                    worker.status = "Disabled (host rejected)"

                # Put incomplete part back for any worker to resume
                if not part.is_complete and self.is_running:
                    self.part_queue.put(part)
            finally:
                self.part_queue.task_done()

    def start(self, progress_callback: Optional[Callable] = None):
        """Starts multi-stream download with NDM part files and final binary assembly."""
        self.is_running = True

        if self.file_size <= 0:
            self.probe_file()

        filename = os.path.basename(self.output_path) or self.suggested_filename
        self.part_manager = SegmentPartManager(
            temp_dir=self.temp_dir,
            filename=filename,
            file_size=self.file_size,
            num_segments=self.num_connections
        )

        parts = self.part_manager.plan_segments()

        # Enqueue incomplete parts
        for part in parts:
            if not part.is_complete:
                self.part_queue.put(part)

        # Distribute threads across adapters (e.g. 16 connections = 8 on Wi-Fi, 8 on Phone USB)
        threads: List[threading.Thread] = []
        num_adapters = max(1, len(self.workers))
        threads_per_worker = max(1, self.num_connections // num_adapters)

        for worker in self.workers.values():
            for _ in range(threads_per_worker):
                t = threading.Thread(target=self._worker_stream, args=(worker,), daemon=True)
                threads.append(t)
                t.start()

        # Monitoring loop (100ms interval for 10 FPS real-time UI updates)
        while any(t.is_alive() for t in threads) and self.is_running:
            time.sleep(0.1)
            
            if self.has_error:
                self.is_running = False
                break

            total_speed = 0.0
            adapter_stats = []
            for worker in self.workers.values():
                speed = worker.update_speed()
                total_speed += speed
                adapter_stats.append({
                    "name": worker.name,
                    "ip": worker.ip,
                    "speed_bps": speed,
                    "total_bytes": worker.total_bytes,
                    "status": worker.status
                })

            downloaded = self.part_manager.get_total_downloaded()
            completed_parts = sum(1 for p in parts if p.is_complete)

            if progress_callback:
                progress_callback({
                    "downloaded_bytes": downloaded,
                    "total_bytes": self.file_size,
                    "completed_parts": completed_parts,
                    "total_parts": len(parts),
                    "total_speed_bps": total_speed,
                    "adapters": adapter_stats,
                    "parts": parts,
                    "is_merging": False,
                    "merge_progress": 0.0,
                    "has_error": self.has_error,
                    "error_message": self.error_message
                })

            if self.part_manager.is_all_complete():
                break

        # Stop worker threads
        for t in threads:
            t.join(timeout=1.0)

        # High-Speed Binary Assembly Phase
        if self.is_running and self.part_manager.is_all_complete():
            self.is_merging = True
            
            def on_merge(prog: float):
                self.merge_progress = prog
                if progress_callback:
                    progress_callback({
                        "downloaded_bytes": self.file_size,
                        "total_bytes": self.file_size,
                        "completed_parts": len(parts),
                        "total_parts": len(parts),
                        "total_speed_bps": 0.0,
                        "adapters": [],
                        "parts": parts,
                        "is_merging": True,
                        "merge_progress": prog,
                        "has_error": False,
                        "error_message": ""
                    })

            self.part_manager.merge_all_parts(self.output_path, progress_callback=on_merge)

        self.is_running = False
        if self.has_error:
            raise RuntimeError(self.error_message)

    def stop(self):
        """Pauses the download and saves all .part files to disk."""
        self.is_running = False
        if self.part_manager:
            self.part_manager.save_metadata()

    def cancel_and_cleanup(self):
        """Stops active workers and completely wipes all .part files and metadata from disk."""
        self.stop()
        if self.part_manager:
            self.part_manager.purge_temp_files()

