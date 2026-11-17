// Exercise setup's actual selection, size calculation and option rendering without a window.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const elements = new Map();
const element = selector => {
  if (!elements.has(selector)) elements.set(selector, { innerHTML: '', querySelectorAll: () => [], focus() {} });
  return elements.get(selector);
};
let source = readFileSync(new URL('../../web/setup.js', import.meta.url), 'utf8');
source = source.replace("load().then(() => { if (view === 'job') poll() });", `
  globalThis.setup = { mapSection, mapAdds, plan, mapIncludes,
    configure(state, selection) { S = state; choice = selection; } };`);
const context = {
  document: { querySelector: element, documentElement: { classList: { contains: () => false } } },
  location: { hash: '' }, addEventListener() {},
};
vm.runInNewContext(source, context);
const setup = context.setup;
const ontario = { id: 'CA-ON', kind: 'province', title: 'Ontario, Canada', available: true, download_bytes: 100, installed_bytes: 200 };
const california = { id: 'CA', kind: 'state', title: 'California', available: true, download_bytes: 50, installed_bytes: 60 };
const guyana = { id: 'GY', kind: 'country', title: 'Guyana', available: true };
const manifest = { maps: [california, ontario, guyana], address_indexes: [], packs: [{ id: 'all', map: 'us', available: true }] };
setup.configure({ manifest, current: { pack: 'all', map: 'us', address_indexes: [] } }, { pack: 'all', map: 'CA-ON', ai: false });
assert.equal(setup.mapAdds().id, 'CA-ON');
assert.equal(setup.plan().dl, 100);
assert.equal(setup.plan().need, 2_000_000_300);
setup.mapSection();
assert.match(element('#mapBox').innerHTML, /Ontario, Canada — 0.0 MB download/);
assert.match(element('#mapBox').innerHTML, /province or state/);
assert.doesNotMatch(element('#mapBox').innerHTML, /value="CA-ON"[^>]*disabled/);
setup.configure({ manifest, current: { pack: 'all', map: 'us', address_indexes: [] } }, { pack: 'all', map: 'CA', ai: false });
assert.equal(setup.mapAdds(), null);
assert.equal(setup.plan().dl, 0);
assert.equal(setup.mapIncludes('us', 'CA-ON'), false);
assert.equal(setup.mapIncludes('us', 'CA'), true);
assert.equal(setup.mapIncludes('us', 'GY'), false);
assert.equal(setup.mapIncludes('CA-ON', 'CA'), false);
console.log('Ontario setup selection, download sizes and existing US coverage pass.');
