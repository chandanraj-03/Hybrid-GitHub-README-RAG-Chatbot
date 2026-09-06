import logging
import re
from typing import List, Dict, Any, Optional
from laptop.app.config import laptop_settings

logger = logging.getLogger("laptop_model")

SYSTEM_GROUNDING_PROMPT = """You are PrivCloud AI, an intelligent, helpful product assistant for PrivCloud.

Answer the user's question accurately, concisely, and professionally using the provided knowledge and context.
Do not invent or hallucinate information.

CRITICAL INSTRUCTIONS:
1. NEVER reveal, cite, or mention where you got the answer from, including any source documents, chunks, files, or underlying references.
2. NEVER mention "README", "README.md", "documentation", "docs", "repository", "repo", "files", "chunks", "context chunks", or specific headings/sections.
3. NEVER say things like "(see the README)", "(based on the context)", "(according to chunk 1)", or include footnote citations like [1], [Context Chunk 1], etc.
4. If information is not available in the context, simply state naturally: "I don't have enough details on that at the moment. Please contact PrivCloud support for more information."
5. Always speak directly and naturally as the official PrivCloud assistant without referencing your internal knowledge retrieval mechanism or underlying sources.
6. DYNAMIC PHRASING & VOCABULARY DIVERSITY:
   - Express ideas using varied phrasing, natural synonyms, and fresh sentence structures across answers.
   - Avoid repetitive, cookie-cutter templates or rigid formulaic openings.
   - You may alternate sentence structure (e.g., active vs. passive, varying introductory clauses, bullet points vs. paragraphs) while preserving 100% strict factual fidelity to the provided context."""


class LaptopTransformerModel:
    """
    Local generative engine utilizing HuggingFace Transformers
    with grounded RAG prompt formatting and graceful fallback.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.model_name = model_name or laptop_settings.LOCAL_MODEL_NAME
        self.device = device or laptop_settings.DEVICE
        self.pipeline = None
        self.tokenizer = None
        self._is_loaded = False

    def load_model(self):
        """Loads HuggingFace transformers model pipeline."""
        if self._is_loaded:
            return

        if laptop_settings.USE_LIGHTWEIGHT_ENGINE:
            logger.info("Using lightweight extractive generator engine for laptop.")
            self._is_loaded = True
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

            device_str = self.device
            if device_str == "auto":
                device_str = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading transformer model '{self.model_name}' on device '{device_str}'...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self.pipeline = pipeline(
                "text-generation",
                model=self.model_name,
                tokenizer=self.tokenizer,
                device=0 if device_str == "cuda" else -1,
                torch_dtype=torch.float16 if device_str == "cuda" else torch.float32,
                trust_remote_code=True,
            )
            self._is_loaded = True
            logger.info(f"Successfully loaded '{self.model_name}'.")
        except Exception as exc:
            logger.warning(
                f"Could not load HuggingFace pipeline for '{self.model_name}' ({exc}). "
                "Enabling lightweight local grounded engine."
            )
            self._is_loaded = True

    def _build_prompt(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        conversation: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Constructs prompt with strict grounding constraints."""
        context_blocks = []
        for i, c in enumerate(context_chunks, 1):
            sec = c.get("section", "Overview")
            txt = c.get("text", "").strip()
            context_blocks.append(f"[Section: {sec}]\n{txt}")

        joined_context = "\n\n".join(context_blocks) if context_blocks else "No README content."

        prompt = (
            f"<|im_start|>system\n{SYSTEM_GROUNDING_PROMPT}\n<|im_end|>\n"
            f"<|im_start|>user\nREADME CONTEXT:\n{joined_context}\n\n"
            f"QUESTION:\n{question}\n<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        return prompt

    def generate_answer(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        conversation: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Generates grounded answer from context."""
        if not self._is_loaded:
            self.load_model()

        if not context_chunks:
            return "I couldn't find that information in the repository README."

        # If Hugging Face pipeline is actively loaded
        if self.pipeline is not None:
            prompt = self._build_prompt(question, context_chunks, conversation)
            try:
                outputs = self.pipeline(
                    prompt,
                    max_new_tokens=laptop_settings.MAX_NEW_TOKENS,
                    temperature=laptop_settings.TEMPERATURE,
                    top_p=getattr(laptop_settings, "TOP_P", 0.9),
                    do_sample=laptop_settings.TEMPERATURE > 0.0,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
                generated = outputs[0]["generated_text"]
                # Extract assistant reply
                if "<|im_start|>assistant" in generated:
                    answer = generated.split("<|im_start|>assistant")[-1].replace("<|im_end|>", "").strip()
                elif "assistant\n" in generated:
                    answer = generated.split("assistant\n")[-1].strip()
                else:
                    answer = generated[len(prompt):].strip()
                return answer if answer else "I couldn't find that information in the repository README."
            except Exception as e:
                logger.error(f"Generation error in transformers pipeline: {e}")

        # Grounded lightweight fallback generator
        return self._grounded_fallback_generate(question, context_chunks)

    def _grounded_fallback_generate(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
    ) -> str:
        """
        Fast deterministic grounded answer generator when full HF weights are uninitialized.
        Strictly answers from context or says "I couldn't find that information in the repository README."
        """
        q_lower = question.lower()
        q_words = set(re.findall(r"\w+", q_lower)) - {"how", "what", "is", "the", "do", "i", "can", "to", "a", "an", "for", "in", "of", "this", "project"}

        best_chunk = None
        best_overlap = 0
        best_matching_lines = []

        for chunk in context_chunks:
            text = chunk.get("text", "")
            sec = chunk.get("section", "Overview")
            lines = text.splitlines()

            for line in lines:
                line_lower = line.lower()
                overlap = sum(1 for w in q_words if w in line_lower)
                if overlap > 0:
                    best_matching_lines.append((overlap, line, sec))

        if not best_matching_lines:
            # Check section header overlap
            for chunk in context_chunks:
                sec = chunk.get("section", "")
                sec_words = set(re.findall(r"\w+", sec.lower()))
                if q_words & sec_words:
                    return f"According to the **{sec}** section in the README:\n\n{chunk.get('text', '').strip()}"
            return "I couldn't find that information in the repository README."

        best_matching_lines.sort(key=lambda x: x[0], reverse=True)
        top_match = best_matching_lines[0]
        sec_name = top_match[2]

        # Find enclosing code block or context in that chunk
        for chunk in context_chunks:
            if chunk.get("section") == sec_name:
                return f"From the **{sec_name}** section in the README:\n\n{chunk.get('text', '').strip()}"

        return f"From README.md ({sec_name}):\n\n{top_match[1].strip()}"
