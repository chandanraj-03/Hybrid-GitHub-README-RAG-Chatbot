"""
Hugging Face Spaces Entrypoint (Gradio SDK).
Combines a Gradio Web UI with the existing FastAPI REST API (/api/chat, /api/health, /docs).
Runs on 16GB RAM with 2 vCPUs on Hugging Face Spaces free tier.
"""

import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from backend.main import app as fastapi_app
from backend.config import BackendConfig
from backend.embeddings import QuestionEmbedder
from backend.generator import AnswerGenerator
from backend.retrieval import ReadmeRetriever
from backend.supabase_client import SupabaseService


def ask_readme_rag(project_id: str, question: str):
    """
    Handler for Gradio UI queries.
    Uses the exact same RAG pipeline as the FastAPI backend.
    """
    if not project_id or not project_id.strip():
        return "⚠️ Please provide a valid Supabase Project ID (UUID).", ""

    if not question or not question.strip():
        return "⚠️ Please enter a question.", ""

    try:
        supabase = SupabaseService.get_instance()
        retriever = ReadmeRetriever(supabase)
        embedder = QuestionEmbedder.get_instance()
        generator = AnswerGenerator.get_instance()

        # 1. Embed query
        q_emb = embedder.embed_question(question.strip())

        # 2. Retrieve context chunks from Supabase
        sources, context = retriever.retrieve(
            project_id=project_id.strip(),
            question_embedding=q_emb,
            top_k=BackendConfig.TOP_K,
            similarity_threshold=BackendConfig.SIMILARITY_THRESHOLD,
        )

        # 3. Generate answer strictly grounded in context
        answer = generator.generate_answer(question.strip(), context)

        # Format retrieved citations for UI
        if sources:
            source_lines = ["### 📚 Cited README Sections:"]
            for s in sources:
                source_lines.append(
                    f"- **{s.section_path}** *(Cosine Similarity: {s.score:.2f})*\n"
                    f"  ```text\n  {s.content[:300]}...\n  ```"
                )
            sources_md = "\n\n".join(source_lines)
        else:
            sources_md = "_No matching README sections met the similarity threshold._"

        return answer, sources_md

    except Exception as e:
        return f"❌ Error executing query: {str(e)}", ""


# Build modern Gradio Web Interface
with gr.Blocks(title="README RAG Chatbot", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🤖 GitHub README RAG Chatbot
        **Lightweight Retrieval-Augmented Generation grounded strictly in GitHub README files.**
        
        *Both the interactive Web UI below and the REST API (`/api/chat`, `/api/health`, `/docs`) are active on this Space.*
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            project_id_input = gr.Textbox(
                label="Project ID (UUID from Supabase)",
                placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000",
                value="",
            )
            question_input = gr.Textbox(
                label="Your Question",
                placeholder="e.g., How do I install and run this project?",
                lines=3,
            )
            submit_btn = gr.Button("🔍 Ask Question", variant="primary")

        with gr.Column(scale=1):
            answer_output = gr.Textbox(
                label="Generated Answer",
                lines=5,
                interactive=False,
            )
            sources_output = gr.Markdown(label="Cited Sources")

    submit_btn.click(
        fn=ask_readme_rag,
        inputs=[project_id_input, question_input],
        outputs=[answer_output, sources_output],
    )

    gr.Markdown(
        """
        ---
        ### 🔌 REST API Endpoints Available:
        - `POST /api/chat` - Query serving endpoint for web widgets & applications
        - `GET /api/health` - Server health check
        - `GET /api/projects/{id}` - Project metadata
        - `GET /docs` - Interactive Swagger API Documentation
        """
    )

# Mount Gradio onto FastAPI: Serves both the Web UI and the REST API on port 7860
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)
