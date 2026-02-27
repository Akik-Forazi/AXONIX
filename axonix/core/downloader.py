"""
axonix Downloader — Background GGUF downloader
"""

import os
import threading
import urllib.request
import time

class ModelDownloader:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ModelDownloader, cls).__new__(cls)
                cls._instance.downloads = {} # {url: {progress, status, total_size, downloaded}}
        return cls._instance

    def download(self, url: str, dest_path: str):
        if url in self.downloads and self.downloads[url]["status"] == "downloading":
            return "Already downloading"

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        self.downloads[url] = {"progress": 0, "status": "downloading", "total_size": 0, "downloaded": 0}
        
        thread = threading.Thread(target=self._run, args=(url, dest_path), daemon=True)
        thread.start()
        return "Started"

    def _run(self, url: str, dest_path: str):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "axonix-Downloader/1.0"})
            with urllib.request.urlopen(req) as resp:
                total = int(resp.headers.get('content-length', 0))
                self.downloads[url]["total_size"] = total
                
                downloaded = 0
                block_size = 1024 * 64
                
                with open(dest_path, "wb") as f:
                    while True:
                        block = resp.read(block_size)
                        if not block:
                            break
                        f.write(block)
                        downloaded += len(block)
                        self.downloads[url]["downloaded"] = downloaded
                        if total > 0:
                            self.downloads[url]["progress"] = int(100 * downloaded / total)
            
            self.downloads[url]["status"] = "complete"
        except Exception as e:
            self.downloads[url]["status"] = f"error: {str(e)}"

    def get_status(self, url: str):
        return self.downloads.get(url, {"status": "not_started"})
