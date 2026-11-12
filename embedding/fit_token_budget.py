"""Build a lossless, model-token-safe derivative of the frozen priority fixture.

Raw parser/chunker exports remain intact. Context headers are repeated on split
records. Exact content offsets and an ID map preserve provenance and QA labels.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from vector_store import MODEL_CONFIGS


def split_record(record, token_count, limit):
    text = record['text']
    if token_count(record['embed_text']) <= limit:
        return [dict(record)]
    # Keep the document/chapter/article header on every segment; the long
    # intro (if present) belongs to content and must itself be split, not lost.
    match = re.search(r'(?m)^(?:Dẫn nhập điều|Khoản [^:\n]+): ', text)
    prefix = text[:match.start()] if match else ''
    content = text[len(prefix):]
    boundaries = [m.end() for m in re.finditer(r'\S+\s*', content)]
    result = []
    start, cursor = 0, 0
    while cursor < len(boundaries):
        low, high, best = cursor, len(boundaries) - 1, None
        while low <= high:
            middle = (low + high) // 2
            candidate = prefix + content[start:boundaries[middle]]
            if token_count(candidate) <= limit:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best is None:
            raise ValueError(f"Header plus a single word exceeds {limit} tokens: {record['id']}")
        end = boundaries[best]
        piece = prefix + content[start:end]
        if token_count(piece) > limit:
            raise ValueError('Token budget invariant failed')
        result.append({**record, 'id': f"{record['id']}_part{len(result) + 1}",
                       'text': piece, 'embed_text': piece,
                       'original_chunk_id': record['id'],
                       'segment_index': len(result) + 1,
                       'source_content_start': start, 'source_content_end': end,
                       'repeated_context_chars': len(prefix)})
        start, cursor = end, best + 1
    if prefix + ''.join(r['text'][len(prefix):] for r in result) != text:
        raise ValueError(f"Content reconstruction failed: {record['id']}")
    return result


def remap_questions(questions, mapping):
    return [{**q, 'relevant_chunk_ids': list(dict.fromkeys(
        new for old in q['relevant_chunk_ids'] for new in mapping[old]))}
        for q in questions]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(__file__).resolve().parent / 'data/priority_chunks.json')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent / 'data')
    args = parser.parse_args()
    from transformers import AutoTokenizer
    from underthesea import word_tokenize
    model = 'bkai-foundation-models/vietnamese-bi-encoder'
    tokenizer = AutoTokenizer.from_pretrained(model)
    limit = MODEL_CONFIGS[model]['max_seq_length']

    def token_count(text):
        prepared = ' '.join(t.replace(' ', '_') for t in word_tokenize(text))
        return len(tokenizer(prepared, truncation=False)['input_ids'])

    source_bytes = args.input.read_bytes()
    source = json.loads(source_bytes)
    chunks, mapping = [], {}
    for record in source['chunks']:
        pieces = split_record(record, token_count, limit)
        mapping[record['id']] = [piece['id'] for piece in pieces]
        chunks.extend(pieces)
    ids = {c['id'] for c in chunks}
    if len(ids) != len(chunks):
        raise ValueError('Duplicate derived chunk IDs')
    lengths = [token_count(c['embed_text']) for c in chunks]
    if max(lengths) > limit:
        raise ValueError('Final token budget validation failed')
    dataset_path = args.output_dir / 'priority_bkai_chunks.json'
    write(dataset_path, {**source, 'dataset_name': 'priority_bkai_token_safe_v1',
                         'parent_dataset_sha256': hashlib.sha256(source_bytes).hexdigest(),
                         'token_budget': {'model': model, 'limit': limit,
                                          'preprocessing': 'underthesea',
                                          'tokenizer_commit': tokenizer.init_kwargs.get('_commit_hash')},
                         'chunks': chunks})
    digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    questions = json.loads((args.input.parent / 'priority_questions.draft.json').read_text(encoding='utf-8'))
    if questions['dataset_sha256'] != hashlib.sha256(source_bytes).hexdigest():
        raise ValueError('Question labels reference a different input fixture')
    remapped = remap_questions(questions['questions'], mapping)
    if any(cid not in ids for q in remapped for cid in q['relevant_chunk_ids']):
        raise ValueError('Unknown remapped label IDs')
    write(args.output_dir / 'priority_bkai_questions.draft.json', {**questions, 'dataset_sha256': digest, 'questions': remapped})
    for split in ['dev', 'test']:
        write(args.output_dir / f'priority_bkai_{split}.draft.json', [q for q in remapped if q['split'] == split])
    write(args.output_dir / 'priority_bkai_id_map.json', {
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'dataset_sha256': digest, 'id_map': mapping,
        'split_original_count': sum(len(v) > 1 for v in mapping.values()),
        'chunk_count_before': len(source['chunks']), 'chunk_count_after': len(chunks),
        'max_tokens_after': max(lengths), 'oversized_after': sum(n > limit for n in lengths),
        'limitation': 'Token-safe splitting preserves parser content, including existing appendix/footer contamination; it does not repair legal structure.'})
    print(json.dumps({'before': len(source['chunks']), 'after': len(chunks),
                      'split_originals': sum(len(v) > 1 for v in mapping.values()),
                      'max_tokens': max(lengths), 'dataset_sha256': digest}))


if __name__ == '__main__':
    main()
