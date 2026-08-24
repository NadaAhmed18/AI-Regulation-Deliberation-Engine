import hashlib
import logging
import os
from pathlib import Path
from helper.config import get_settings, Settings
from .RetrivalEnum import ContentTypeEnum
from .RetrievalSchema import UrlDocument
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
import pdfplumber
import io


class Scrapdata:

    def __init__(self, config: Settings, delays_sec: int = None, timeout_sec: int = None):
        self.config = config
        self.header = {"User-Agent": self.config.USER_AGENT}
        self.delays_sec = self.config.REQUEST_DELAY_SECONDS if not delays_sec else delays_sec
        self.timeout_sec = self.config.REQUEST_TIMEOUT_SECONDS if not timeout_sec else timeout_sec
        self.root_dir = Path(__file__).resolve().parents[2]
        self.raw_dir = os.path.join(self.root_dir, "data", "raw")
        
        os.makedirs(self.raw_dir, exist_ok=True)

    @staticmethod
    def _doc_id(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def check_url_request(self, url: str) -> httpx.Response | None:
        logging.info(f"Async requesting URL via httpx: {url}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, 
                    headers=self.header, 
                    timeout=self.timeout_sec,
                    follow_redirects=True
                )
            response.raise_for_status() 
            return response
            
        except httpx.HTTPStatusError as status_err:
            logging.error(f"HTTP status error occurred for {url}: {status_err}")
            if status_err.response.status_code < 500:
                return status_err.response
            raise status_err
            
        except httpx.ConnectError as conn_err:
            logging.error(f"Connection error occurred for URL {url}: {conn_err}")
            raise conn_err
            
        except httpx.TimeoutException as timeout_err:
            logging.error(f"Timeout occurred for URL {url}: {timeout_err}")
            raise timeout_err
            
        except httpx.RequestError as req_err:
            logging.error(f"An error occurred while requesting {url}: {req_err}")
            return None

    async def is_pdf_url(self, url: str) -> bool:
        logging.info(f"Checking if URL is a PDF: {url}")
        try:
            response = await self.check_url_request(url)
            if response is None:
                logging.warning(f"Could not fetch URL headers for: {url}")
                return False
            
            content_type = response.headers.get("content-type", "").lower()
            if ContentTypeEnum.PDF.value in content_type:
                logging.info(f"URL is a valid PDF: {url}")
                return True
            return False
        except Exception as err:
            logging.error(f"Unexpected error checking if URL is PDF for {url}: {err}")
            return False

    async def is_html_url(self, url: str) -> bool:
        logging.info(f"Checking if URL is a HTML: {url}")
        try:
            response = await self.check_url_request(url)
            if response is None:
                logging.warning(f"Could not fetch URL headers for: {url}")
                return False
            
            content_type = response.headers.get("content-type", "").lower()
            if ContentTypeEnum.HTML.value in content_type:
                logging.info(f"URL is a valid HTML: {url}")
                return True
            return False
        except Exception as err:
            logging.error(f"Unexpected error checking if URL is HTML for {url}: {err}")
            return False

    async def scrap_pdf_url(self, url: str) -> tuple[UrlDocument, str] | None:
        logging.info(f"Starting memory-based PDF text extraction for: {url}")
        
        is_pdf = await self.is_pdf_url(url)
        if not is_pdf:
            return None

        response = await self.check_url_request(url)
        if response is None:
            return None

        text_parts: list[str] = []
        doc_id = self._doc_id(url)

        try:
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")
            
            extracted_text = "\n".join(text_parts).strip()
            file_path = os.path.join(self.raw_dir, f"{doc_id}.pdf")

            url_document = UrlDocument(
                id=doc_id,
                source_type=ContentTypeEnum.PDF.value,
                source_url=url,
                title=url.split("/")[-1] or "PDF Document",
                raw_text=extracted_text
            )
            
            logging.info(f"Successfully processed PDF text for {url}")
            return url_document, file_path
            
        except Exception as e:
            logging.error(f"Failed to extract text from PDF for {url}: {e}")
            return None

    async def scrap_html_url(self, url: str) -> tuple[UrlDocument, str] | None:
        logging.info(f"Starting HTML content scraping for: {url}")
        
        is_html = await self.is_html_url(url)
        if not is_html:
            return None

        response = await self.check_url_request(url)
        if response is None:
            return None

        doc_id = self._doc_id(url)
        file_path = os.path.join(self.raw_dir, f"{doc_id}.html")

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.extract()
                
            page_title = soup.title.string.strip() if soup.title else (url.split("/")[-1] or "Web Page")
            extracted_text = soup.get_text(separator="\n", strip=True)
            
            url_document = UrlDocument(
                id=doc_id,
                source_type=ContentTypeEnum.HTML.value,
                source_url=url,
                title=page_title,
                raw_text=extracted_text
            )
            
            logging.info(f"Successfully processed HTML for {url}")
            return url_document, file_path
            
        except Exception as e:
            logging.error(f"Failed to process HTML content for {url}: {e}")
            return None

    @staticmethod
    def save_document(raw_text: str, file_path: str) -> bool:
  
        try:
            folder_path = os.path. dirname(file_path)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
            return True
        except Exception as e:
            logging.error(f"Failed to save text in this {file_path}: {e}")
            return False
