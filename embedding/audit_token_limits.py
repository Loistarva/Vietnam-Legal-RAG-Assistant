"""Measure fixture token lengths with model tokenizers without loading weights."""
import argparse
import json
from pathlib import Path

from vector_store import MODEL_CONFIGS, chunk_file_sha256, load_chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chunks', type=Path, default=Path(__file__).resolve().parent / 'data/priority_chunks.json')
    parser.add_argument('--model', choices=list(MODEL_CONFIGS), default='bkai-foundation-models/vietnamese-bi-encoder')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    config = MODEL_CONFIGS[args.model]
    chunks = load_chunks(args.chunks)
    texts = [c['embed_text'] for c in chunks]
    if config['preprocess'] == 'underthesea':
        from underthesea import word_tokenize
        texts = [' '.join(t.replace(' ', '_') for t in word_tokenize(text)) for text in texts]
    lengths = tokenizer(texts, truncation=False, padding=False, return_length=True)['length']
    oversized = [{'chunk_id': c['chunk_id'], 'tokens': length}
                 for c, length in zip(chunks, lengths) if length > config['max_seq_length']]
    report = {'model': args.model, 'dataset_sha256': chunk_file_sha256(args.chunks),
              'chunk_count': len(chunks), 'limit': config['max_seq_length'],
              'max_tokens': max(lengths), 'oversized_count': len(oversized),
              'oversized': oversized,
              'note': 'Includes special tokens and model-specific preprocessing; no model weights or retrieval metrics.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'oversized'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
