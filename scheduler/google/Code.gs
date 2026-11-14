/** Google clock -> GitHub workflow. Never requests Amazon or sends email. */
const PSN_REPO = 'olcaysadik/psn-stock-bot';
const PSN_WORKFLOW = 'monitor.yml';
const PSN_HANDLER = 'dispatchPsnMonitor';

function testPsnDispatch() {
  return dispatchPsn_('manual_test');
}

function dispatchPsnMonitor(event) {
  const properties = PropertiesService.getScriptProperties();
  if (properties.getProperty('SCHEDULER_ENABLED') !== 'true') {
    console.log('PSN scheduler paused');
    return {accepted: false, paused: true};
  }
  return dispatchPsn_(event && event.triggerUid ? 'time_trigger' : 'manual');
}

function installPsnScheduler() {
  // A failed credential test never creates/enables a recurring trigger.
  const result = testPsnDispatch();
  if (!result.accepted) {
    throw new Error('No verified dispatch; recurring scheduler was not installed');
  }
  const triggers = ScriptApp.getProjectTriggers().filter(function(trigger) {
    return trigger.getHandlerFunction() === PSN_HANDLER &&
      trigger.getEventType() === ScriptApp.EventType.CLOCK;
  });
  if (triggers.length > 1) {
    throw new Error('Multiple PSN clock triggers found; remove duplicates in Triggers first');
  }
  if (triggers.length === 0) {
    ScriptApp.newTrigger(PSN_HANDLER).timeBased().everyMinutes(10).create();
  }
  PropertiesService.getScriptProperties().setProperty('SCHEDULER_ENABLED', 'true');
  console.log('PSN Google clock installed: every 10 minutes');
  return result;
}

function pausePsnScheduler() {
  PropertiesService.getScriptProperties().setProperty('SCHEDULER_ENABLED', 'false');
  console.log('PSN Google clock paused; no GitHub requests will be made');
}

function psnSchedulerStatus() {
  const properties = PropertiesService.getScriptProperties();
  const status = {};
  ['SCHEDULER_ENABLED', 'LAST_DISPATCH_UTC', 'LAST_DISPATCH_SOURCE',
   'LAST_DISPATCH_RUN_ID', 'LAST_DISPATCH_RUN_URL', 'LAST_DISPATCH_ERROR'].forEach(function(key) {
    status[key] = properties.getProperty(key) || '';
  });
  console.log(JSON.stringify(status));
  return status;
}

function dispatchPsn_(source) {
  const properties = PropertiesService.getScriptProperties();
  const token = (properties.getProperty('GITHUB_DISPATCH_TOKEN') || '').trim();
  if (!token || /\s/.test(token)) {
    throw new Error('GITHUB_DISPATCH_TOKEN is missing or has invalid whitespace; use Script Properties');
  }
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) {
    console.log('PSN dispatch skipped: another call is still running');
    return {accepted: false, busy: true};
  }
  try {
    let response;
    try {
      response = UrlFetchApp.fetch(
        'https://api.github.com/repos/' + PSN_REPO + '/actions/workflows/' + PSN_WORKFLOW + '/dispatches',
        {
          method: 'post', contentType: 'application/json',
          headers: {
            Accept: 'application/vnd.github+json',
            Authorization: 'Bearer ' + token,
            'X-GitHub-Api-Version': '2026-03-10'
          },
          payload: JSON.stringify({ref: 'main', inputs: {mode: 'monitor'}}),
          validateHttpsCertificates: true, followRedirects: false,
          muteHttpExceptions: true, timeoutSeconds: 30
        }
      );
    } catch (error) {
      properties.setProperty('LAST_DISPATCH_ERROR', 'Network request failed; no automatic retry');
      // Never print the exception, request headers, token or response body.
      throw new Error('PSN dispatch network failure; inspect GitHub before retrying');
    }
    const code = response.getResponseCode();
    if (code !== 200 && code !== 204) {
      properties.setProperty('LAST_DISPATCH_ERROR', 'GitHub HTTP ' + code);
      throw new Error('PSN dispatch rejected: GitHub HTTP ' + code);
    }
    let data = {};
    if (code === 200) {
      try { data = JSON.parse(response.getContentText()); } catch (error) { /* accepted; metadata absent */ }
    }
    const runId = /^\d+$/.test(String(data.workflow_run_id || '')) ? String(data.workflow_run_id) : '';
    const runUrl = runId ? 'https://github.com/' + PSN_REPO + '/actions/runs/' + runId : '';
    const acceptedAt = new Date().toISOString();
    properties.setProperties({
      LAST_DISPATCH_UTC: acceptedAt, LAST_DISPATCH_SOURCE: source,
      LAST_DISPATCH_RUN_ID: runId, LAST_DISPATCH_RUN_URL: runUrl, LAST_DISPATCH_ERROR: ''
    });
    console.log(JSON.stringify({accepted: true, source: source, http: code, utc: acceptedAt, run_url: runUrl}));
    return {accepted: true, http: code, run_url: runUrl};
  } finally {
    lock.releaseLock();
  }
}
