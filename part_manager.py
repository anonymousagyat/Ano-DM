"""
NDM-Style Segment Part Manager
Handles calculation of byte segments, per-part temporary files (.part0, .part1, ...),
resume byte detection, and high-speed binary sequential assembly.
"""

import os
import json
import shutil
from typing import List, Dict, Any, Callable, Optional


class SegmentPart:
    def __init__(self, part_id: int, orig_start: int, orig_end: int, path: str):
        self.part_id = part_id
        self.orig_start = orig_start
        self.orig_end = orig_end
        self.total_size = (orig_end - orig_start + 1)
        self.path = path
        
        # Check existing downloaded bytes for instant resume
        existing = os.path.getsize(path) if os.path.exists(path) else 0
        if existing > self.total_size:
            existing = self.total_size  # Sanity check

        self.downloaded_bytes = existing
        self.current_start = orig_start + existing
        self.is_complete = (self.downloaded_bytes >= self.total_size)
        self.status = "Completed" if self.is_complete else "Pending"
        self.assigned_adapter = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "part_id": self.part_id,
            "orig_start": self.orig_start,
            "orig_end": self.orig_end,
            "total_size": self.total_size,
            "downloaded_bytes": self.downloaded_bytes,
            "current_start": self.current_start,
            "is_complete": self.is_complete,
            "path": self.path
        }


class SegmentPartManager:
    def __init__(self, temp_dir: str, filename: str, file_size: int, num_segments: int):
        self.temp_dir = temp_dir
        self.filename = filename
        self.file_size = file_size
        self.num_segments = max(1, num_segments)
        self.meta_path = os.path.join(temp_dir, f"{filename}.ndm.json")
        os.makedirs(temp_dir, exist_ok=True)
        self.parts: List[SegmentPart] = []

    def plan_segments(self) -> List[SegmentPart]:
        """
        Slices the file into N independent segments and checks for existing .part files.
        """
        self.parts = []
        part_size = self.file_size // self.num_segments
        
        for i in range(self.num_segments):
            start = i * part_size
            end = (self.file_size - 1) if (i == self.num_segments - 1) else (start + part_size - 1)
            part_path = os.path.join(self.temp_dir, f"{self.filename}.part{i}")
            part = SegmentPart(i, start, end, part_path)
            self.parts.append(part)

        self.save_metadata()
        return self.parts

    def save_metadata(self):
        """Persists segment state to a metadata JSON file for resume tracking."""
        try:
            data = {
                "filename": self.filename,
                "file_size": self.file_size,
                "num_segments": self.num_segments,
                "parts": [p.to_dict() for p in self.parts]
            }
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def get_total_downloaded(self) -> int:
        return sum(p.downloaded_bytes for p in self.parts)

    def is_all_complete(self) -> bool:
        return all(p.is_complete for p in self.parts)

    def merge_all_parts(self, final_output_path: str, progress_callback: Optional[Callable[[float], None]] = None):
        """
        Sequentially concatenates all .part files into the final destination file,
        then cleans up the temporary part files and metadata.
        """
        final_dir = os.path.dirname(os.path.abspath(final_output_path))
        os.makedirs(final_dir, exist_ok=True)

        buffer_size = 4 * 1024 * 1024  # 4 MB binary copy buffer for fast assembly
        merged_bytes = 0

        with open(final_output_path, "wb") as outfile:
            for part in self.parts:
                if os.path.exists(part.path):
                    with open(part.path, "rb") as infile:
                        while True:
                            chunk = infile.read(buffer_size)
                            if not chunk:
                                break
                            outfile.write(chunk)
                            merged_bytes += len(chunk)
                            if progress_callback and self.file_size > 0:
                                progress_callback(merged_bytes / self.file_size)

        # Cleanup temporary .part files and metadata after successful assembly
        for part in self.parts:
            try:
                if os.path.exists(part.path):
                    os.remove(part.path)
            except Exception:
                pass

        try:
            if os.path.exists(self.meta_path):
                os.remove(self.meta_path)
        except Exception:
            pass

    def purge_temp_files(self):
        """Purges all .part files and metadata associated with this download from disk."""
        for part in self.parts:
            try:
                if os.path.exists(part.path):
                    os.remove(part.path)
            except Exception:
                pass
        try:
            if os.path.exists(self.meta_path):
                os.remove(self.meta_path)
        except Exception:
            pass

