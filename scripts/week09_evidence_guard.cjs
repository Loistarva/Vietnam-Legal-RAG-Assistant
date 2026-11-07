// Validate captured evidence before emitting any PASS claims.
const EXPECTED_PRS = [25, 26, 27, 28, 29, 32];
const COMMANDS = [
  ['scripts/validate_benchmark.py'],
  ['scripts/freeze_test.py', '--verify'],
  ['scripts/freeze_gold.py', '--verify'],
  ['-m', 'pytest', '-q'],
];
function validateEvidence(snapshots, api, tests, probe) {
  if (!api.observed_at || !Array.isArray(api.details)) throw Error('Missing GitHub metadata');
  if (api.details.length !== EXPECTED_PRS.length || new Set(api.details.map(p=>p.number)).size !== EXPECTED_PRS.length)
    throw Error('Incomplete or duplicate PR metadata');
  for (const number of EXPECTED_PRS) {
    const pr = api.details.find(p=>p.number === number);
    const snapshot = snapshots.find(s=>s.ref === `origin/pr/${number}`);
    if (!pr || !snapshot || snapshot.sha !== pr.head_sha) throw Error(`API/ref SHA mismatch PR ${number}`);
  }
  for (const name of ['testing', 'pr25', 'pr27', 'pr32']) {
    const result = tests[name];
    const snapshot = snapshots.find(s=>s.ref === (name === 'testing' ? 'origin/testing' : `origin/pr/${name.slice(2)}`));
    if (!result || !snapshot || result.sha !== snapshot.sha || result.sha_after !== result.sha)
      throw Error(`Stale or changed checkout: ${name}`);
    if (result.tracked_status_before !== '' || result.tracked_status_after !== '')
      throw Error(`Dirty or unproven checkout: ${name}`);
    if (!Array.isArray(result.results) || result.results.length !== COMMANDS.length)
      throw Error(`Missing checks: ${name}`);
    result.results.forEach((check, i)=> {
      if (JSON.stringify(check.args) !== JSON.stringify(COMMANDS[i]) || check.exit_code !== 0 || typeof check.stdout !== 'string')
        throw Error(`Failed/incomplete check: ${name}/${i}`);
    });
    if (!snapshot.questions_freeze_match || !snapshot.gold_freeze_match)
      throw Error(`Freeze mismatch: ${name}`);
  }
  const pr32 = snapshots.find(s=>s.ref === 'origin/pr/32');
  if (!probe || probe.source_sha !== pr32.sha || probe.tracked_status_after !== '' ||
      probe.real_model_calls !== 0 || probe.real_test_queries_read !== 0)
    throw Error('Stale or unsafe zero-shot probe evidence');
}
module.exports = { validateEvidence, COMMANDS, EXPECTED_PRS };
