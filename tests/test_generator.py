"""
Unit tests for Generator and Hallucination Control.
"""

from unittest.mock import MagicMock, patch
import pytest

from backend.generator import AnswerGenerator, FALLBACK_ANSWER


def test_build_prompt_structure():
    generator = AnswerGenerator.__new__(AnswerGenerator)
    question = "What database is used?"
    context = "### Section: Database\nPostgreSQL is used with pgvector."

    prompt = generator.build_prompt(question, context)
    assert "You are a project documentation assistant." in prompt
    assert "README CONTEXT:" in prompt
    assert context in prompt
    assert "QUESTION:\nWhat database is used?" in prompt
    assert 'respond exactly: "I couldn\'t find that information in the README.md."' in prompt


def test_empty_context_triggers_fallback():
    generator = AnswerGenerator.__new__(AnswerGenerator)
    
    # Test empty string and whitespace context
    ans1 = generator.generate_answer("What is this?", "")
    ans2 = generator.generate_answer("What is this?", "   ")

    assert ans1 == FALLBACK_ANSWER
    assert ans2 == FALLBACK_ANSWER


def test_generator_mocked_generation():
    generator = AnswerGenerator.__new__(AnswerGenerator)
    generator.device = "cpu"
    generator.tokenizer = MagicMock()
    generator.model = MagicMock()

    # Mock tokenizer output
    generator.tokenizer.return_value = {"input_ids": MagicMock()}
    generator.model.generate.return_value = ["dummy_token_ids"]
    generator.tokenizer.decode.return_value = "The project uses FastAPI and PostgreSQL."

    ans = generator.generate_answer(
        "What technologies are used?", 
        "### Section: Tech Stack\nFastAPI and PostgreSQL."
    )
    assert ans == "The project uses FastAPI and PostgreSQL."


def test_generator_refusal_normalization():
    generator = AnswerGenerator.__new__(AnswerGenerator)
    generator.device = "cpu"
    generator.tokenizer = MagicMock()
    generator.model = MagicMock()

    generator.tokenizer.return_value = {"input_ids": MagicMock()}
    generator.model.generate.return_value = ["dummy_token_ids"]
    
    # Model generates a refusal variation
    generator.tokenizer.decode.return_value = "I couldn't find that information in the context."

    ans = generator.generate_answer(
        "What is the CEO name?",
        "### Section: Tech Stack\nFastAPI and PostgreSQL."
    )
    assert ans == FALLBACK_ANSWER
