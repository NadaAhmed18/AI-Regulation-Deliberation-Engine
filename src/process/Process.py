import os
import re
from pathlib import Path
from bs4 import BeautifulSoup

class ProcessData:
    def __init__(self, root_dir: Path = None):
        self.root_dir = Path(__file__).resolve().parents[2]
        self.clean_dir = os.path.join(self.root_dir, "data", "process")
        
        os.makedirs(self.clean_dir, exist_ok=True)

    def clean_text(self, text: str) -> str:
       
        if not text:
            return ""

        # 1. Strip any missed HTML/XML tags safely using BeautifulSoup logic or regex fallback
        text = BeautifulSoup(text, "html.parser").get_text()
        text = re.sub(r'<[^>]+>', '', text)

        # 2. Normalize whitespace, tabs, and duplicate newlines
        text = re.sub(r'[ \t]+', ' ', text)  # Collapse horizontal spaces
        text = re.sub(r'\n\s*\n+', '\n\n', text)  # Collapse excessive vertical spacing

        # 3. Clean encoding glitches or control characters while keeping standard text/punctuation
        text = text.encode("utf-8", errors="ignore").decode("utf-8")

        return text.strip()
