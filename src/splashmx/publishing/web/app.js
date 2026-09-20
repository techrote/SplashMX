const form = document.querySelector('#load-form');
const locator = document.querySelector('#locator');
const role = document.querySelector('#locator-role');
const status = document.querySelector('#status');
const active = document.querySelector('#active');

async function loadCreation() {
  status.textContent = 'Preparing immutable creation…';
  const response = await fetch('/api/load', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mode: role.value, value: locator.value})
  });
  const payload = await response.json();
  if (!response.ok) {
    status.textContent = `Load failed: ${payload.error.code}`;
    if (payload.state && payload.state.active) active.textContent = JSON.stringify(payload.state.active, null, 2);
    return;
  }
  active.textContent = JSON.stringify(payload.active, null, 2);
  active.dataset.revision = payload.active.creation_revision_id;
  status.textContent = `Ready: ${payload.active.creation_revision_id}`;
}

form.addEventListener('submit', (event) => { event.preventDefault(); loadCreation().catch((error) => { status.textContent = `Load failed: ${error.name}`; }); });
