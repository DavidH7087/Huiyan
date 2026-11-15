"""Optional CPU Chinese semantic encoder: explicit provisioning, no resume uploads.

The retrieval path never downloads a model: local_files_only=True. Provisioning
is a separate deliberate action and downloads only model assets, not candidate
files. External model/license information lives in docs/FASTEMBED_SETUP.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MODEL_NAME = 'BAAI/bge-small-zh-v1.5'


class FastEmbedEncoder:
    """Bridge FastEmbed's streaming .embed() to SemanticMatcher's .encode()."""

    def __init__(self, cache_dir: str | Path, *, allow_download: bool = False):
        from fastembed import TextEmbedding
        cache = Path(cache_dir).expanduser()
        if not cache.is_dir() and not allow_download:
            raise FileNotFoundError('Local Chinese embedding model cache not present')
        cache.mkdir(parents=True, exist_ok=True)
        # Bound threads on regular HR laptops to avoid starving the interface.
        self._model = TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=str(cache),
            local_files_only=not allow_download,
            threads=2,
        )

    def encode(self, sentences, **kwargs):
        # No request payloads are sent over the network. The runtime only uses
        # the local ONNX model prepared by the user/packaging pipeline.
        texts = [str(x)[:2000] for x in sentences]
        if not texts:
            return []
        return list(self._model.embed(texts, batch_size=16))


def provision_model(cache_dir: str | Path):
    """Explicit opt-in download for a one-time setup, never called by screening."""
    model = FastEmbedEncoder(cache_dir, allow_download=True)
    embeddings = model.encode(['企业客户开发经验'])
    if len(embeddings) != 1 or len(embeddings[0]) != 512:
        raise RuntimeError('Embedding model returned unexpected dimensions')
    return {'model': MODEL_NAME, 'dimensions': 512, 'offline_ready': True}


def main():
    cli = argparse.ArgumentParser(description='Install optional Chinese offline embedding model')
    cli.add_argument('action', choices=['prepare'])
    cli.add_argument('--cache-dir', required=True)
    args = cli.parse_args()
    print(provision_model(args.cache_dir))


if __name__ == '__main__':
    main()
