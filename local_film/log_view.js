let logSources = [];
let logJob = '';
const logBox = document.querySelector('#logs');
const sourceSelect = document.querySelector('#logSource');
const filterSelect = document.querySelector('#logFilter');
const followLog = document.querySelector('#followLog');

function logLevel(line) {
  if (/\b(error|exception|traceback|failed|outofmemory)\b|out of memory/i.test(line)) return 'error';
  if (/\b(warning|warn)\b/i.test(line)) return 'warning';
  if (/^\d{1,3}%\|/.test(line)) return 'progress';
  return 'info';
}

function visibleLogLines() {
  const source = logSources.find(s => s.id === sourceSelect.value);
  return (source?.lines || []).filter(line => filterSelect.value !== 'issues' || ['error', 'warning'].includes(logLevel(line)));
}

function renderLog() {
  const source = logSources.find(s => s.id === sourceSelect.value);
  const lines = visibleLogLines();
  const scrollTop = logBox.scrollTop;
  const fragment = document.createDocumentFragment();
  for (const line of lines) {
    const row = document.createElement('div');
    row.className = 'log-line log-' + logLevel(line);
    row.textContent = line;
    fragment.append(row);
  }
  if (!lines.length) {
    const empty = document.createElement('div');
    empty.className = 'log-empty';
    empty.textContent = filterSelect.value === 'issues' ? 'No warnings or errors in the recent log.' : 'Waiting for log output…';
    fragment.append(empty);
  }
  logBox.replaceChildren(fragment);
  logBox.scrollTop = followLog.checked ? logBox.scrollHeight : scrollTop;
  document.querySelector('#logNote').textContent = source?.shared
    ? 'Shared ComfyUI log — may include other local jobs. Sampling percentages describe a pass, not the whole video.'
    : 'Output from the selected job only. Shows the most recent 200 lines.';
}

function updateLog(response, jobId) {
  if (logJob !== jobId) {
    logJob = jobId;
    followLog.checked = true;
  }
  logSources = response.sources || [{id: 'comfy', title: 'Combined log', lines: [response.text || '']}];
  renderLog();
  document.querySelector('#logUpdated').textContent = 'Updated ' + new Date().toLocaleTimeString();
}

sourceSelect.onchange = renderLog;
filterSelect.onchange = renderLog;
followLog.onchange = renderLog;
logBox.onscroll = () => {
  if (logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight > 40) followLog.checked = false;
};
document.querySelector('#copyLog').onclick = async () => {
  try {
    await navigator.clipboard.writeText(visibleLogLines().join('\n'));
    document.querySelector('#logUpdated').textContent = 'Log copied';
  } catch (error) {
    document.querySelector('#logUpdated').textContent = 'Copy unavailable; select and copy the log text.';
  }
};
