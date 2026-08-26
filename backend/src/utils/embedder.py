import os
import re
import numpy as np
from typing import List
from src.config import MAX_CHARS, MAX_CHUNKS, SLIDING_SENTENCES

try:
    from config import VECTOR_DIMENSION
except ImportError:
    VECTOR_DIMENSION = int(os.environ.get("VECTOR_DIMENSION", 1024))

class Embedder:
    _hf_cache = {}

    def __init__(self, model_name: str, model_type: str = "voyage"):
        self.model_name = model_name
        self.model_type = model_type.lower()
        
        if self.model_type == "voyage":
            import voyageai
            api_key = os.environ.get("VOYAGE_API_KEY")
            if not api_key:
                raise ValueError("VOYAGE_API_KEY missing from environment variables.")
            self.client = voyageai.Client(api_key=api_key) # type: ignore
            
        elif self.model_type == "hf":
            if self.model_name not in self._hf_cache:
                import torch
                from sentence_transformers import SentenceTransformer
                device = "cuda" if torch.cuda.is_available() else "cpu"
                dtype = torch.bfloat16 if device == "cuda" else torch.float32
                self._hf_cache[self.model_name] = SentenceTransformer(
                    self.model_name, model_kwargs={"torch_dtype": dtype}, trust_remote_code=True
                )
            self.hf_model = self._hf_cache[self.model_name]
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def chunk_text(self, text: str) -> List[str]:
        """
        Splits a long document into overlapping chunks based on sentences.
        Respects MAX_CHARS per chunk and SLIDING_SENTENCES for overlap.
        Stops extracting if MAX_CHUNKS limit is reached.
        """
        # Split text by punctuation (. ! ?) while keeping the punctuation attached to the sentence
        raw_sentences = re.split(r'(?<=[.!?])(?:\s+|\n+)', text)
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        if not sentences:
            return []

        chunks = []
        current_chunk = []
        current_length = 0

        i = 0
        while i < len(sentences):
            sentence = sentences[i]
            sentence_len = len(sentence) + 1  # +1 accounts for the space between sentences

            # Edge case: A single sentence is larger than MAX_CHARS
            if sentence_len > MAX_CHARS:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                    if len(chunks) >= MAX_CHUNKS: break
                
                # Hard truncate the massive sentence and add as its own chunk
                chunks.append(sentence[:MAX_CHARS])
                if len(chunks) >= MAX_CHUNKS: break
                i += 1
                continue

            # If adding this sentence exceeds the limit, finalize the current chunk
            if current_length + sentence_len > MAX_CHARS:
                chunks.append(" ".join(current_chunk))
                if len(chunks) >= MAX_CHUNKS: 
                    break
                
                # Slide back for context overlap (e.g., keep the last 2 sentences)
                overlap = current_chunk[-SLIDING_SENTENCES:] if SLIDING_SENTENCES > 0 else []
                current_chunk = overlap
                current_length = sum(len(s) + 1 for s in overlap)
                # Notice we do NOT increment `i` here, because the current sentence 
                # still needs to be added to the new chunk.
            else:
                current_chunk.append(sentence)
                current_length += sentence_len
                i += 1

        # Add any remaining sentences as the final chunk
        if current_chunk and len(chunks) < MAX_CHUNKS:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _smart_truncate(self, text: str, max_chars: int = MAX_CHARS) -> str:
        """Acts as an absolute safety net for the embed function."""
        if len(text) <= max_chars:
            return text
            
        truncated = text[:max_chars]
        matches = list(re.finditer(r'[.!?](?:\s|\n|$)', truncated))
        if matches:
            return truncated[:matches[-1].end()].strip()
            
        last_space = truncated.rfind(' ')
        if last_space > -1:
            return truncated[:last_space].strip()
            
        return truncated 

    def embed(self, texts: List[str], is_query: bool = False) -> np.ndarray:
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, VECTOR_DIMENSION)
            
        # _smart_truncate is applied here just in case a chunk bypassed the chunker limit
        safe_texts = [self._smart_truncate(t) for t in texts]

        if self.model_type == "voyage":
            return self._embed_voyage(safe_texts, is_query)
        return self._embed_hf(safe_texts, is_query)

    def _embed_voyage(self, texts: List[str], is_query: bool) -> np.ndarray:
        input_type = "query" if is_query else "document"
        embeddings = []
        
        for i in range(0, len(texts), 64):
            batch = texts[i : i + 64]
            try:
                result = self.client.embed(
                    texts=batch,
                    model=self.model_name,
                    input_type=input_type,
                    output_dimension=VECTOR_DIMENSION,
                    output_dtype="float"
                )
                embeddings.extend(result.embeddings)
            except Exception as e:
                print(f"[-] Voyage API Error: {e}")
                embeddings.extend([[0.0] * VECTOR_DIMENSION] * len(batch))
                
        emb_array = np.array(embeddings, dtype=np.float32)
        
        norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
        emb_array = np.divide(emb_array, norms, out=np.zeros_like(emb_array), where=norms!=0)
        
        return emb_array

    def _embed_hf(self, texts: List[str], is_query: bool) -> np.ndarray:
        import torch
        
        if is_query:
            texts = [f"search_query: {t}" for t in texts]
            
        all_embeddings = []
        for i in range(0, len(texts), 4):
            batch = texts[i : i + 4]
            # HF natively normalizes when normalize_embeddings=True
            embs = self.hf_model.encode(batch, convert_to_numpy=True, normalize_embeddings=True)
            all_embeddings.append(embs)
            torch.cuda.empty_cache()
            
        return np.concatenate(all_embeddings, axis=0)