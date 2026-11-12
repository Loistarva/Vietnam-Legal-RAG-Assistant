"""Verify the two observed cached BGE weight formats have identical tensors.

Run after inference to avoid CPU/I/O contention. The base snapshot and the
safetensors-only snapshot are read-only; no model code is executed from pickle.
"""
import hashlib
import json
from pathlib import Path

import torch
from safetensors import safe_open

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.venv-embedding/hf-cache/hub/models--BAAI--bge-m3'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def main():
    revision = (CACHE / 'refs/main').read_text().strip()
    binary = CACHE / 'snapshots' / revision / 'pytorch_model.bin'
    alternatives = [p for p in (CACHE / 'snapshots').iterdir()
                    if (p / 'model.safetensors').exists() and p.name != revision]
    if len(alternatives) != 1:
        raise ValueError('Expected the one safetensors-only snapshot observed in this run')
    alternative = alternatives[0]
    safefile = alternative / 'model.safetensors'
    weights = torch.load(binary, map_location='cpu', weights_only=True, mmap=True)
    with safe_open(safefile, framework='pt', device='cpu') as other:
        if set(weights) != set(other.keys()):
            raise ValueError('Weight tensor keys differ')
        for key, tensor in weights.items():
            candidate = other.get_tensor(key)
            if tensor.dtype != candidate.dtype or not torch.equal(tensor, candidate):
                raise ValueError(f'Weight tensor differs: {key}')
    report = {'model': 'BAAI/bge-m3', 'main_revision': revision,
              'additional_safetensors_snapshot': alternative.name,
              'tensor_count': len(weights), 'all_tensor_values_and_dtypes_equal': True,
              'pytorch_bin_sha256': digest(binary), 'safetensors_sha256': digest(safefile),
              'method': 'Read-only torch.load(weights_only=True, mmap=True) and safetensors; exact torch.equal for every tensor.'}
    target = ROOT / 'data/structure_v2/benchmark/bge_weight_equivalence.json'
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
