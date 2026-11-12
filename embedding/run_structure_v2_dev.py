"""Run sequential CPU Dev evaluations against the frozen structure-v2 corpus.

Requires all three models cached under HF_HOME (offline by default). Results
and hashes are versioned separately; no baseline or Test files are overwritten.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/structure_v2/embedding'
OUTPUT = ROOT / 'data/structure_v2/benchmark'
MODELS = [('bkai', 'bkai-foundation-models/vietnamese-bi-encoder'),
          ('aiteamvn', 'AITeamVN/Vietnamese_Embedding'), ('bge_m3', 'BAAI/bge-m3')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    fixture = DATA / 'priority_bkai_chunks.json'
    labels = DATA / 'priority_bkai_dev.draft.json'
    judgments = json.loads(labels.read_text(encoding='utf-8'))
    baseline = json.loads((ROOT / 'embedding/data/priority_bkai_dev.support_reviewed.json').read_text(encoding='utf-8'))
    semantic = lambda rows: [(q['question_id'], q['query'], sorted(q['relevant_chunk_ids'])) for q in rows]
    if semantic(judgments) != semantic(baseline) or len(judgments) != 10 or any(q['split'] != 'dev' for q in judgments):
        raise ValueError('Dev semantics differ from the baseline, or a non-Dev query is present')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.setdefault('HF_HOME', str(ROOT / '.venv-embedding/hf-cache'))
    environment.setdefault('HF_HUB_OFFLINE', '1')
    environment['PYTHONUTF8'] = '1'
    status = {'dataset_sha256': digest(fixture), 'labels_sha256': digest(labels),
              'dev_semantics_equal_to_baseline': True, 'test_evaluated': False,
              'execution': 'sequential CPU; batch size 32', 'models': {}}

    def save():
        with (OUTPUT / 'run_status.json').open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(status, ensure_ascii=False, indent=2) + '\n')

    for slug, model in MODELS:
        snapshot_dir = Path(environment['HF_HOME']) / 'hub' / ('models--' + model.replace('/', '--')) / 'snapshots'
        status['models'][slug] = {'model': model, 'stage': 'token_audit',
                                  'cached_main_revision': (snapshot_dir.parent / 'refs/main').read_text().strip(),
                                  'observed_cache_snapshots': sorted(p.name for p in snapshot_dir.iterdir() if p.is_dir())}
        save()
        commands = [
            ('token_audit', [sys.executable, str(ROOT / 'embedding/audit_token_limits.py'),
                            '--chunks', str(fixture), '--model', model,
                            '--output', str(OUTPUT / f'{slug}_token_audit.json')]),
            ('dev', [sys.executable, str(ROOT / 'embedding/retrieval_smoke_test.py'),
                     '--chunks', str(fixture), '--ground-truth', str(labels), '--model', model,
                     '--device', 'cpu', '--batch-size', '32',
                     '--results', str(OUTPUT / f'{slug}_dev.json')]),
        ]
        environment['QDRANT_PATH'] = str(ROOT / 'qdrant_data/structure_v2' / slug)
        for stage, command in commands:
            status['models'][slug]['stage'] = stage
            save()
            print(f'{slug}: {stage}', flush=True)
            with (OUTPUT / f'{slug}_{stage}.log').open('w', encoding='utf-8') as log:
                completed = subprocess.run(command, cwd=ROOT, env=environment,
                                           stdout=log, stderr=subprocess.STDOUT)
            if completed.returncode:
                status['models'][slug]['stage'] = 'failed_' + stage
                status['models'][slug]['exit_code'] = completed.returncode
                save()
                raise RuntimeError(f'{slug} {stage} failed; inspect {OUTPUT / (slug + "_" + stage + ".log")}')
            if stage == 'token_audit':
                audit = json.loads((OUTPUT / f'{slug}_token_audit.json').read_text(encoding='utf-8'))
                if audit['dataset_sha256'] != status['dataset_sha256'] or audit['oversized_count']:
                    raise ValueError('Tokenizer audit does not validate the current corpus')
        result = json.loads((OUTPUT / f'{slug}_dev.json').read_text(encoding='utf-8'))
        if result['chunk_file_sha256'] != status['dataset_sha256'] or result['ground_truth_sha256'] != status['labels_sha256']:
            raise ValueError('Result hashes differ from the frozen run inputs')
        status['models'][slug]['stage'] = 'complete'
        status['models'][slug]['metrics'] = result['ground_truth_metrics']
        save()
        print(f'{slug}: complete {json.dumps(result["ground_truth_metrics"])}', flush=True)
    status['complete'] = True
    save()


if __name__ == '__main__':
    main()
