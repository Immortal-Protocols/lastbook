import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const context = {};
vm.runInNewContext(readFileSync(process.argv[2], 'utf8'), context);
const included = context.SetupMap.included;
const state = { id: 'CA', kind: 'state' };
const spain = { id: 'ES', kind: 'country' };
assert.equal(included('us', state), true);
assert.equal(included('us', spain), false);
assert.equal(included('ES', spain), true);
assert.equal(included('ES', state), false);
assert.equal(included('CA', state), true);
assert.equal(included('base', spain), false);
assert.equal(context.SetupMap.packMap('all', {map: null}), 'us');
assert.equal(context.SetupMap.packMap('all', {map: 'base'}), null);
assert.equal(context.SetupMap.packMap('medium', {map: null}), 'CA');
assert.equal(context.SetupMap.packMap('medium', {map: 'ES'}), 'ES');
assert.equal(context.SetupMap.packMap('small', {map: null}), null);

// Setup should apply a later country manifest without requiring a page reload.
const tasks = [], seen = [];
const states = [
  {manifest: {fetching: true, maps: [{id: 'ES', available: false}]}},
  {manifest: {fetching: false, maps: [{id: 'ES', available: true}]}},
];
context.SetupMap.followManifest(async () => states.shift(), state => seen.push(state), fn => tasks.push(fn));
assert.equal(tasks.length, 1);
await tasks.shift()();
assert.equal(seen[0].manifest.maps[0].available, false);
assert.equal(tasks.length, 1);
await tasks.shift()();
assert.equal(seen[1].manifest.maps[0].available, true);
assert.equal(tasks.length, 0);
