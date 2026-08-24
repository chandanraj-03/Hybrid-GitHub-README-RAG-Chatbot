"""
Local Indexing CLI.
Executes the GPU-accelerated README indexing pipeline:
1. Validates GitHub URL and downloads README.
2. Computes SHA-256 hash.
3. Performs intelligent Markdown-aware hierarchical chunking.
4. Generates normalized vector embeddings via NVIDIA GPU (CUDA) or CPU.
5. Uploads chunks and metadata to Supabase pgvector.

Usage:
    python index_project.py --github https://github.com/owner/repo
    python index_project.py --github https://github.com/owner/repo --force
    python index_project.py --gpu-info
"""

import argparse
from pathlib import Path
import sys
import time
from typing import Optional

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

indexer_dir = Path(__file__).resolve().parent
if str(indexer_dir) not in sys.path:
    sys.path.insert(0, str(indexer_dir))

from indexer.config import IndexerConfig
from indexer.github_reader import GitHubReader, GitHubURLError, ReadmeFetchError
from indexer.markdown_chunker import MarkdownChunker
from indexer.embedding_generator import EmbeddingGenerator
from indexer.supabase_uploader import SupabaseUploader


def print_banner() -> None:
    print("=" * 50)
    print("        README-BASED RAG LOCAL INDEXER        ")
    print("=" * 50)


def print_gpu_info() -> None:
    print("\n[GPU & Compute Diagnostics]")
    gpu_info = IndexerConfig.get_gpu_info()
    if gpu_info.get("cuda_available"):
        print(f"  CUDA Available     : Yes")
        print(f"  GPU Device Name    : {gpu_info.get('device_name')}")
        print(f"  Device Count       : {gpu_info.get('device_count')}")
        print(f"  Compute Capability : {gpu_info.get('compute_capability')}")
        print(f"  VRAM               : {gpu_info.get('vram_gb')} GB")
        print(f"  PyTorch Version    : {gpu_info.get('pytorch_version')}")
    else:
        print(f"  CUDA Available     : No")
        print(f"  Compute Device     : {gpu_info.get('device_name')}")
        print(f"  PyTorch Version    : {gpu_info.get('pytorch_version')}")
    print("=" * 50 + "\n")


def run_indexer(
    github_url: str,
    force: bool = False,
    model_name: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    start_time = time.time()
    print_banner()

    # 1. Validate & Download README
    print(f"\n[1/5] Fetching README for repository: {github_url}")
    try:
        raw_readme, readme_hash, readme_url, owner, repo_name = GitHubReader.fetch_readme(github_url)
        print(f"  Repository : {owner}/{repo_name}")
        print(f"  README URL : {readme_url}")
        print(f"  SHA-256    : {readme_hash[:16]}...")
        print(f"  Size       : {len(raw_readme)} characters ({len(raw_readme.encode('utf-8'))} bytes)")
    except (GitHubURLError, ReadmeFetchError) as e:
        print(f"\n[ERROR] Failed to fetch README: {str(e)}", file=sys.stderr)
        sys.exit(1)

    # 2. Check Supabase for existing project and hash matching
    target_model = model_name or IndexerConfig.DEFAULT_EMBEDDING_MODEL
    uploader = None
    existing_project = None

    if not dry_run:
        try:
            uploader = SupabaseUploader()
            normalized_url, _, _ = GitHubReader.parse_github_url(github_url)
            existing_project = uploader.get_project_by_github(normalized_url)
            
            should_idx, reason = uploader.should_reindex(
                existing_project, 
                readme_hash, 
                target_model, 
                force=force
            )
            
            print(f"\n[2/5] Checking Re-indexing Status:")
            print(f"  Decision : {'Re-indexing needed' if should_idx else 'Skipping indexing'}")
            print(f"  Reason   : {reason}")

            if not should_idx:
                print("\n" + "=" * 50)
                print("README has not changed. No re-indexing required.")
                print("==================================================")
                return

        except Exception as e:
            print(f"\n[WARNING] Supabase connection check warning: {str(e)}")
            print("Proceeding with local processing...")
    else:
        print("\n[2/5] Dry Run Mode: Skipping Supabase remote check.")

    # 3. Intelligent Markdown Chunking
    c_size = chunk_size or IndexerConfig.CHUNK_SIZE
    c_overlap = chunk_overlap or IndexerConfig.CHUNK_OVERLAP
    print(f"\n[3/5] Performing Hierarchical Markdown Chunking...")
    print(f"  Target Chunk Size    : {c_size} chars")
    print(f"  Target Chunk Overlap : {c_overlap} chars")

    chunker = MarkdownChunker(chunk_size=c_size, chunk_overlap=c_overlap)
    chunks = chunker.chunk_markdown(raw_readme)
    print(f"  Generated Chunks     : {len(chunks)}")

    if not chunks:
        print("\n[ERROR] No chunks produced from README. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Sample chunk preview
    print(f"  First Section Path   : {chunks[0].section_path}")
    print(f"  Last Section Path    : {chunks[-1].section_path}")

    # 4. Generate Embeddings using NVIDIA GPU / CUDA
    print(f"\n[4/5] Loading Transformer Embedding Model...")
    active_device = IndexerConfig.get_device()
    print(f"  Model Name  : {target_model}")
    print(f"  Device      : {active_device.upper()}")
    
    if active_device == "cuda":
        gpu_details = IndexerConfig.get_gpu_info()
        print(f"  GPU Name    : {gpu_details.get('device_name')}")

    embedder = EmbeddingGenerator(model_name=target_model, device=active_device)
    embedding_dim = embedder.get_dimension()
    print(f"  Vector Dim  : {embedding_dim}")

    print(f"  Generating embeddings for {len(chunks)} chunks...")
    chunk_texts = [c.content for c in chunks]
    embeddings = embedder.generate_embeddings(chunk_texts, show_progress_bar=True)
    print(f"  Embeddings generated successfully. ({len(embeddings)} vectors)")

    # 5. Upload to Supabase
    if dry_run:
        print("\n[5/5] Dry Run Mode: Skipping upload to Supabase.")
        print(f"Would have created/updated project with {len(chunks)} chunks.")
    else:
        print(f"\n[5/5] Uploading to Supabase PostgreSQL (pgvector)...")
        if uploader is None:
            uploader = SupabaseUploader()
            
        normalized_url, _, _ = GitHubReader.parse_github_url(github_url)
        project_id = uploader.upsert_project(
            github_url=normalized_url,
            owner=owner,
            repo_name=repo_name,
            readme_hash=readme_hash,
            readme_url=readme_url,
            embedding_model=target_model,
            embedding_dimension=embedding_dim,
        )
        print(f"  Project ID  : {project_id}")

        # Delete existing chunks if updating
        if existing_project:
            print("  Cleaning up prior chunks...")
            uploader.delete_project_chunks(project_id)

        print(f"  Uploading {len(chunks)} vector records...")
        uploaded_count = uploader.upload_chunks(project_id, chunks, embeddings)
        print(f"  Uploaded    : {uploaded_count} chunks")

    elapsed = round(time.time() - start_time, 2)
    print("\n" + "=" * 50)
    print(f"Indexing completed successfully in {elapsed}s.")
    print("=" * 50 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local GPU-accelerated README indexer for RAG Chatbot"
    )
    parser.add_argument(
        "--github",
        type=str,
        help="Public GitHub repository URL (e.g. https://github.com/owner/repo)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-indexing even if the README SHA-256 hash has not changed",
    )
    parser.add_argument(
        "--gpu-info",
        action="store_true",
        help="Print diagnostic information about NVIDIA GPU and CUDA availability",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Custom SentenceTransformer embedding model (default: sentence-transformers/all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Target maximum character chunk size (default: 800)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=None,
        help="Target chunk overlap in characters (default: 150)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute parsing, chunking, and embedding without connecting or uploading to Supabase",
    )

    args = parser.parse_args()

    if args.gpu_info:
        print_banner()
        print_gpu_info()
        if not args.github:
            sys.exit(0)

    if not args.github:
        parser.print_help()
        sys.exit(1)

    run_indexer(
        github_url=args.github,
        force=args.force,
        model_name=args.model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
