const form = document.getElementById('gen-form');
const result = document.getElementById('result');
const jobs = document.getElementById('jobs');
const refreshBtn = document.getElementById('refresh-btn');

function escapeHtml(str) {
  return (str || '').replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[m]));
}

function renderJob(job) {
  const refs = (job.reference_files || []).map(name => `<span class="chip">${escapeHtml(name)}</span>`).join(' ');
  const preview = job.preview_url
    ? `<div class="preview"><video controls src="${escapeHtml(job.preview_url)}"></video></div>`
    : '';

  return `
    <article class="job-card">
      <div class="job-top">
        <strong>${escapeHtml(job.status || 'unknown')}</strong>
        <span>${escapeHtml(job.created_at || '')}</span>
      </div>
      <p><strong>Duration:</strong> ${escapeHtml(String(job.duration))} sec</p>
      <p><strong>Aspect:</strong> ${escapeHtml(job.aspect_ratio || '')} &nbsp; <strong>Resolution:</strong> ${escapeHtml(job.resolution || '')}</p>
      <p><strong>Provider mode:</strong> ${escapeHtml(job.provider_mode || '')}</p>
      <p><strong>Message:</strong> ${escapeHtml(job.message || '')}</p>
      <details>
        <summary>Prompt</summary>
        <pre>${escapeHtml(job.prompt || '')}</pre>
      </details>
      <details>
        <summary>Optimized prompt</summary>
        <pre>${escapeHtml(job.optimized_prompt || '')}</pre>
      </details>
      <div class="chips">${refs || '<span class="muted">No references uploaded</span>'}</div>
      ${preview}
    </article>
  `;
}

async function loadJobs() {
  jobs.innerHTML = '<p class="muted">Loading jobs...</p>';
  const res = await fetch('/api/jobs');
  const data = await res.json();
  if (!Array.isArray(data) || data.length === 0) {
    jobs.innerHTML = '<p class="muted">No jobs yet.</p>';
    return;
  }
  jobs.innerHTML = data.map(renderJob).join('');
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  result.classList.remove('hidden');
  result.innerHTML = '<p class="muted">Submitting...</p>';

  const fd = new FormData(form);
  const res = await fetch('/api/generate', {
    method: 'POST',
    body: fd,
  });
  const data = await res.json();

  if (!res.ok) {
    result.innerHTML = `<p>Something went wrong.</p><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
    return;
  }

  result.innerHTML = `
    <h3>Job submitted</h3>
    <p><strong>Status:</strong> ${escapeHtml(data.status || '')}</p>
    <p><strong>Message:</strong> ${escapeHtml(data.message || '')}</p>
    <details open>
      <summary>Optimized prompt</summary>
      <pre>${escapeHtml(data.optimized_prompt || '')}</pre>
    </details>
  `;

  form.reset();
  loadJobs();
});

refreshBtn.addEventListener('click', loadJobs);
loadJobs();
