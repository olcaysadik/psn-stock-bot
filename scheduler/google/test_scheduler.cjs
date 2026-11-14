const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(__dirname + '/Code.gs', 'utf8');

function harness(options = {}) {
  const values = {GITHUB_DISPATCH_TOKEN: 'test-token-value', ...options.values};
  const calls = [], messages = [], created = [];
  let released = 0;
  const properties = {
    getProperty: key => values[key],
    setProperty: (key, value) => { values[key] = value; },
    setProperties: data => { Object.assign(values, data); }
  };
  const context = vm.createContext({
    Date, JSON, console: {log: value => messages.push(String(value))},
    PropertiesService: {getScriptProperties: () => properties},
    LockService: {getScriptLock: () => ({tryLock: () => options.busy !== true, releaseLock: () => released++})},
    ScriptApp: {
      EventType: {CLOCK: 'CLOCK'},
      getProjectTriggers: () => options.triggers || [],
      newTrigger: handler => ({timeBased: () => ({everyMinutes: minutes => ({create: () => created.push({handler, minutes})})})})
    },
    UrlFetchApp: {fetch: (url, request) => {
      calls.push({url, request});
      if (options.error) throw new Error(options.error);
      return {getResponseCode: () => options.status || 200,
        getContentText: () => options.body || '{"workflow_run_id":12345}'};
    }}
  });
  vm.runInContext(code, context);
  return {context, values, calls, messages, created, released: () => released};
}

test('installation sends a safe request, creates a ten-minute clock and records metadata', () => {
  const h = harness();
  assert.equal(h.context.installPsnScheduler().accepted, true);
  assert.equal(h.calls.length, 1);
  const {url, request} = h.calls[0];
  assert.equal(url, 'https://api.github.com/repos/olcaysadik/psn-stock-bot/actions/workflows/monitor.yml/dispatches');
  assert.deepEqual(JSON.parse(request.payload), {ref: 'main', inputs: {mode: 'monitor'}});
  assert.equal(request.validateHttpsCertificates, true);
  assert.equal(request.followRedirects, false);
  assert.equal(request.timeoutSeconds, 30);
  assert.deepEqual(h.created, [{handler: 'dispatchPsnMonitor', minutes: 10}]);
  assert.equal(h.values.SCHEDULER_ENABLED, 'true');
  assert.equal(h.values.LAST_DISPATCH_RUN_ID, '12345');
  assert.equal(h.released(), 1);
  assert.ok(h.messages.every(message => !message.includes('test-token-value')));
});

test('the real clock handler identifies time-driven events', () => {
  const h = harness({values: {SCHEDULER_ENABLED: 'true'}});
  h.context.dispatchPsnMonitor({triggerUid: 'clock-id'});
  assert.equal(h.values.LAST_DISPATCH_SOURCE, 'time_trigger');
});

test('pausing prevents network calls and status never exposes the token', () => {
  const h = harness({values: {SCHEDULER_ENABLED: 'true'}});
  h.context.pausePsnScheduler();
  assert.equal(h.context.dispatchPsnMonitor({triggerUid: 'clock-id'}).paused, true);
  assert.equal(h.calls.length, 0);
  assert.ok(!JSON.stringify(h.context.psnSchedulerStatus()).includes('test-token-value'));
});

test('an existing clock is reused rather than duplicated', () => {
  const h = harness({triggers: [{getHandlerFunction: () => 'dispatchPsnMonitor', getEventType: () => 'CLOCK'}]});
  h.context.installPsnScheduler();
  assert.equal(h.created.length, 0);
});

test('HTTP errors never enable the schedule and never disclose response text', () => {
  const h = harness({status: 401, body: 'private-secret-from-response'});
  assert.throws(() => h.context.installPsnScheduler(), /GitHub HTTP 401/);
  assert.equal(h.values.SCHEDULER_ENABLED, undefined);
  assert.equal(h.created.length, 0);
  assert.ok(!h.messages.join('').includes('private-secret-from-response'));
  assert.equal(h.released(), 1);
});

test('ambiguous network failures are not retried and sensitive exceptions are suppressed', () => {
  const h = harness({error: 'test-token-value in transport error'});
  assert.throws(() => h.context.testPsnDispatch(), error => !error.message.includes('test-token-value'));
  assert.equal(h.calls.length, 1);
  assert.equal(h.released(), 1);
});

test('missing token and overlapping calls make no request', () => {
  const missing = harness({values: {GITHUB_DISPATCH_TOKEN: ''}});
  assert.throws(() => missing.context.installPsnScheduler(), /GITHUB_DISPATCH_TOKEN/);
  assert.equal(missing.calls.length, 0);
  const busy = harness({busy: true});
  assert.equal(busy.context.testPsnDispatch().busy, true);
  assert.equal(busy.calls.length, 0);
  assert.throws(() => busy.context.installPsnScheduler(), /No verified dispatch/);
  assert.equal(busy.created.length, 0);
  assert.equal(busy.values.SCHEDULER_ENABLED, undefined);
});

test('legacy 204 responses are accepted without parsing a body', () => {
  const h = harness({status: 204});
  assert.equal(h.context.testPsnDispatch().accepted, true);
  assert.equal(h.values.LAST_DISPATCH_RUN_ID, '');
});
