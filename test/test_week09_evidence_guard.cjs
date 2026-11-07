const { test } = require('node:test');
const assert = require('node:assert/strict');
const { validateEvidence, COMMANDS, EXPECTED_PRS } = require('../scripts/week09_evidence_guard.cjs');
function fixture() {
  const snapshots = ['origin/testing', ...EXPECTED_PRS.map(n=>`origin/pr/${n}`)]
    .map((ref, i)=>({ref, sha:`sha${i}`, questions_freeze_match:true, gold_freeze_match:true}));
  const api = {observed_at:'2026-11-06T00:00:00Z', details:EXPECTED_PRS.map((number,i)=>({number,head_sha:`sha${i+1}`}))};
  const tests = Object.fromEntries(['testing','pr25','pr27','pr32'].map(name=> {
    const sha=snapshots.find(s=>s.ref === (name==='testing'?'origin/testing':`origin/pr/${name.slice(2)}`)).sha;
    return [name,{sha,sha_after:sha,tracked_status_before:'',tracked_status_after:'',
      results:COMMANDS.map(args=>({args:[...args],exit_code:0,stdout:'PASS'}))}];
  }));
  return [snapshots, api, tests, {source_sha:snapshots.at(-1).sha,tracked_status_after:'',real_model_calls:0,real_test_queries_read:0}];
}
test('accept complete evidence tied to the exact clean checkouts',()=>assert.doesNotThrow(()=>validateEvidence(...fixture())));
test('reject nonzero and timed-out check exits',()=> {
  for(const code of [1,null]) {const f=fixture();f[2].pr25.results[3].exit_code=code;assert.throws(()=>validateEvidence(...f),/Failed/);}
});
test('reject logs without post-run identity and cleanliness proof',()=> {
  const f=fixture();delete f[2].pr27.tracked_status_after;assert.throws(()=>validateEvidence(...f),/Dirty or unproven/);
});
test('reject checkout modified during checks',()=> {
  const f=fixture();f[2].testing.tracked_status_after=' M data/benchmark/ground_truth.json';assert.throws(()=>validateEvidence(...f),/Dirty/);
});
test('reject checkout moved to a different commit during checks',()=> {
  const f=fixture();f[2].pr27.sha_after='another-commit';assert.throws(()=>validateEvidence(...f),/Stale or changed/);
});
test('reject incomplete checks and a substituted command',()=> {
  const f=fixture();f[2].pr32.results.pop();assert.throws(()=>validateEvidence(...f),/Missing/);
  const g=fixture();g[2].pr32.results[3].args=['-m','pytest','one_test.py'];assert.throws(()=>validateEvidence(...g),/Failed/);
});
test('reject stale SHA in test logs, API or probe',()=> {
  const f=fixture();f[2].pr27.sha='old';assert.throws(()=>validateEvidence(...f),/Stale/);
  const g=fixture();g[1].details[0].head_sha='old';assert.throws(()=>validateEvidence(...g),/SHA mismatch/);
  const h=fixture();h[3].source_sha='old';assert.throws(()=>validateEvidence(...h),/probe/);
});
test('reject duplicate PR metadata and freeze failure',()=> {
  const f=fixture();f[1].details[0]=f[1].details[1];assert.throws(()=>validateEvidence(...f),/duplicate/);
  const g=fixture();g[0][0].gold_freeze_match=false;assert.throws(()=>validateEvidence(...g),/Freeze/);
});
