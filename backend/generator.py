"""
Lightweight Generator Module for Render Backend.
Loads google/flan-t5-small once at startup and performs grounded RAG generation on CPU.
Enforces hallucination control and fallback behaviors.
"""

from typing import Optional
from backend.config import BackendConfig

FALLBACK_ANSWER = "I couldn't find that information in the README.md."


class AnswerGenerator:
    _instance: Optional["AnswerGenerator"] = None

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or BackendConfig.GENERATOR_MODEL_NAME
        self.device = "cpu"
        self.tokenizer = None
        self.model = None
        self._load_model()

    @classmethod
    def get_instance(cls) -> "AnswerGenerator":
        """Singleton accessor to ensure the generation model is loaded only once."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self) -> None:
        """Loads Hugging Face tokenizer and model on CPU or CUDA."""
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForCausalLM, AutoConfig
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

        config = AutoConfig.from_pretrained(self.model_name)
        self.is_causal = config.is_encoder_decoder is False

        if self.is_causal:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32 if self.device == "cpu" else torch.float16,
            ).to(self.device)
        else:
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name).to(self.device)

        self.model.eval()

    def build_prompt(self, question: str, retrieved_context: str) -> str:
        """Constructs a strict grounded RAG prompt optimized for the active model architecture."""
        system_msg = (
            "You are a project documentation assistant.\n"
            "Answer the user's question clearly and accurately using ONLY the provided README context.\n"
            "Do not use outside knowledge or invent information.\n"
            'If the answer is not present in the README context, respond exactly: "I couldn\'t find that information in the README.md."'
        )

        if getattr(self, "is_causal", False) and hasattr(self.tokenizer, "apply_chat_template"):
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"README CONTEXT:\n{retrieved_context}\n\nQUESTION:\n{question}"},
            ]
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        # FLAN-T5 Seq2Seq optimization (fine-tuned format for compact models)
        return (
            "Answer the following question using only the provided context. If not found, say I couldn't find that information in the README.md.\n\n"
            f"Context:\n{retrieved_context}\n\n"
            f"Question:\n{question}\n\n"
            "Answer:"
        )

    def generate_answer(self, question: str, retrieved_context: str) -> str:
        """
        Generates a concise, grounded answer based strictly on retrieved README context.
        """
        # Hallucination Guard 1: If context is empty, refuse immediately
        if not retrieved_context or not retrieved_context.strip():
            return FALLBACK_ANSWER

        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Generator model is not initialized.")

        import torch

        prompt = self.build_prompt(question, retrieved_context)
        raw_inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048,
        )

        if hasattr(raw_inputs, "to"):
            inputs = raw_inputs.to(self.device)
        elif isinstance(raw_inputs, dict):
            inputs = {
                k: (v.to(self.device) if hasattr(v, "to") else v)
                for k, v in raw_inputs.items()
            }
        else:
            inputs = raw_inputs

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                repetition_penalty=1.1,
            )

        # For Causal LMs (like Qwen), decode only the newly generated tokens
        if getattr(self, "is_causal", False):
            input_len = inputs["input_ids"].shape[1]
            generated_tokens = outputs[0][input_len:]
            answer = self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
        else:
            answer = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

        # Hallucination Guard 2: Post-process generated answer
        if not answer:
            return FALLBACK_ANSWER

        answer_lower = answer.lower()
        if (
            "couldn't find that information" in answer_lower
            or "not mentioned in the readme" in answer_lower
            or "not provided in the context" in answer_lower
            or answer == "unanswerable"
        ):
            return FALLBACK_ANSWER

        return answer
