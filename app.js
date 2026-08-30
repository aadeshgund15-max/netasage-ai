const state = { cases: [], selected: null, lastDiagnosis: null };
const $ = (id) => document.getElementById(id);

async function api(url, options={}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function esc(s='') { 
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])); 
}

function renderMetrics(summary) {
  const map = {};
  summary.forEach(r => { map[`${r.section}:${r.key}`] = Number(r.value); });
  const total = Object.keys(map).filter(k=>k.startsWith('review_status:')).reduce((a,k)=>a+map[k],0);
  const yes = map['ai_vs_expected:yes'] || 0;
  $('metrics').innerHTML = [
    ['Cases', total, 'troubleshooting scenarios'],
    ['AI agreement', `${total ? ((yes/total)*100).toFixed(1) : 0}%`, `${yes} of ${total} cases matched`],
    ['Human accepted', map['review_status:Accepted'] || 0, 'review decisions'],
    ['Rules', 6, 'deterministic checks']
  ].map(x=>`<div class="metric"><strong>${esc(x[1])}</strong><span>${esc(x[0])} · ${esc(x[2])}</span></div>`).join('');
}

function renderCases() {
  const q = $('caseSearch').value.toLowerCase();
  const list = state.cases.filter(c => `${c.case_id} ${c.symptom} ${c.concept_tag}`.toLowerCase().includes(q));
  $('caseCount').textContent = state.cases.length;
  $('caseList').innerHTML = list.map(c => `<div class="case-item ${state.selected?.case_id===c.case_id?'active':''}" data-id="${esc(c.case_id)}"><span class="id">${esc(c.case_id)}</span><strong>${esc(c.symptom)}</strong><small>${esc(c.concept_tag)} · ${esc(c.severity)}</small></div>`).join('');
  document.querySelectorAll('.case-item').forEach(el => el.onclick = () => selectCase(el.dataset.id));
}

async function selectCase(id) {
  state.selected = state.cases.find(c=>c.case_id===id);
  renderCases();
  $('caseTitle').textContent = state.selected.symptom;
  $('runBtn').disabled = false;
  $('caseMeta').innerHTML = `<span class="meta">${esc(state.selected.case_id)}</span><span class="meta">${esc(state.selected.concept_tag)}</span><span class="meta">Severity: ${esc(state.selected.severity)}</span><span class="meta">OSI Layer ${esc(state.selected.osi_layer)}</span>`;
  $('symptomBox').innerHTML = `<strong>Topology:</strong> ${esc(state.selected.topology_note)}<br><br><strong>Symptom:</strong> ${esc(state.selected.symptom)}<br><br><strong>Show output:</strong><br><code>${esc(state.selected.show_outputs)}</code>`;
  $('resultArea').classList.add('hidden');
  $('reviewMessage').textContent = '';
  await runDiagnosis();
}

function renderDiagnosis(data) {
  state.lastDiagnosis = data;
  const d = data.diagnosis || {};

  $('rootCause').textContent = d.root_cause || data.category || 'Diagnostic Finding';
  $('confidence').textContent = `${d.confidence || data.confidence || 'medium'} confidence`;
  
  if ($('evidence')) {
    $('evidence').innerHTML = (d.evidence || []).map(x => `<li>${esc(x)}</li>`).join('');
  }
  
  if ($('nextCommand')) {
    $('nextCommand').textContent = d.next_command || data.next_command || 'N/A';
  }

  // Render Fix Steps
  if ($('fixSteps')) {
    const steps = d.fix_steps || [];
    $('fixSteps').innerHTML = steps.length 
      ? steps.map(x => `<li>${esc(x)}</li>`).join('') 
      : '<li>No explicit fix steps provided.</li>';
  }

  // Render Rule Findings & Remediation Solutions
  if ($('ruleFindings')) {
    const findings = data.rule_findings || data.findings || [];
    if (findings.length > 0) {
      $('ruleFindings').innerHTML = findings.map(f => `
        <div class="finding" style="margin-bottom: 8px;">
          <strong>${esc(f.rule || 'Issue Detected')}</strong> — ${esc(f.detail || '')}
          ${f.solution ? `
            <div style="margin-top: 6px; padding: 8px; background: rgba(0, 255, 170, 0.08); border-left: 3px solid #00ffaa; border-radius: 4px;">
              <strong style="color: #00ffaa;">Remediation Solution:</strong>
              <pre style="margin-top: 4px; white-space: pre-wrap; font-family: monospace; font-size: 0.9em; color: #e0e0e0;">${esc(f.solution)}</pre>
            </div>
          ` : ''}
        </div>
      `).join('');
    } else {
      $('ruleFindings').innerHTML = '<div class="finding ok">No deterministic configuration issue detected by the six rules.</div>';
    }
  }

  if ($('agreement')) {
    $('agreement').className = `agreement ${data.agreement === true ? 'yes' : 'no'}`;
    $('agreement').textContent = data.agreement === true 
      ? '✓ AI-style diagnosis agrees with the expected fault family.' 
      : '△ AI-style diagnosis does not exactly match the expected fault. Human review is recommended.';
  }

  if ($('reviewFault')) {
    $('reviewFault').value = (data.case && data.case.expected_fault) ? data.case.expected_fault : '';
  }

  $('resultArea').classList.remove('hidden');
}

async function runDiagnosis() {
  if (!state.selected) return;
  $('runBtn').disabled = true; $('runBtn').textContent = 'Analyzing…';
  try { renderDiagnosis(await api(`/api/cases/${state.selected.case_id}`)); }
  catch(e) { $('reviewMessage').textContent = e.message; }
  finally { $('runBtn').disabled = false; $('runBtn').innerHTML = 'Analyze case <span>→</span>'; }
}

async function saveReview() {
  if (!state.selected) return;
  $('saveReview').disabled = true;
  try {
    const data = await api('/api/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        case_id: state.selected.case_id,
        review_status: $('reviewStatus').value,
        review_notes: $('reviewNotes').value,
        final_fault: $('reviewFault').value
      })
    });
    $('reviewMessage').textContent = '✓ ' + data.message;
    renderMetrics((await api('/api/summary')).summary);
  } catch(e) { $('reviewMessage').textContent = 'Error: ' + e.message; }
  finally { $('saveReview').disabled = false; }
}

async function customDiagnosis() {
  const symptom = $('customSymptom').value.trim(); 
  const show = $('customShow').value.trim();
  
  if (!symptom && !show) { 
    $('customResult').classList.remove('hidden'); 
    $('customResult').textContent = 'Enter a symptom or show output first.'; 
    return; 
  }
  
  $('customBtn').disabled = true; 
  $('customBtn').textContent = 'Analyzing…';
  
  try {
    const data = await api('/api/diagnose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_id: 'CUSTOM', symptom, show_outputs: show, expected_fault: '' })
    });
    
    const d = data.diagnosis || {};
    const findings = data.rule_findings || data.findings || [];
    
    let findingsHTML = '';
    if (findings.length > 0) {
      findingsHTML = findings.map(f => `
        <div style="margin-top: 10px; padding: 10px; background: rgba(0, 255, 170, 0.08); border-left: 3px solid #00ffaa; border-radius: 4px;">
          <strong style="color: #00ffaa;">Rule: ${esc(f.rule || '')}</strong> — ${esc(f.detail || '')}
          ${f.solution ? `
            <div style="margin-top: 6px; font-size: 0.9em; color: #e0e0e0;">
              <strong>Remediation Steps:</strong>
              <pre style="margin-top: 4px; white-space: pre-wrap; font-family: monospace; background: rgba(0,0,0,0.3); padding: 6px; border-radius: 4px; color: #a5f3fc;">${esc(f.solution)}</pre>
            </div>
          ` : ''}
        </div>
      `).join('');
    }

    const rootCauseText = d.root_cause || data.category || 'Diagnosis Result';
    const confidenceText = d.confidence || data.confidence || 'medium';
    const nextCmdText = d.next_command || data.next_command || 'show ip interface brief';
    const evidenceList = (d.evidence || []);

    $('customResult').innerHTML = `
      <h3>${esc(rootCauseText)}</h3>
      <p style="color: #a0a0a0; font-size: 0.9em;">Confidence: <strong>${esc(confidenceText)}</strong> · Next command: <code>${esc(nextCmdText)}</code></p>
      ${symptom ? `<p style="margin-top: 8px;"><strong>Symptom observed:</strong> ${esc(symptom)}</p>` : ''}
      ${evidenceList.length ? `<p style="margin-top: 6px;">${evidenceList.map(esc).join('<br>')}</p>` : ''}
      ${findingsHTML}
    `;
    $('customResult').classList.remove('hidden');
  } catch(e) { 
    $('customResult').textContent = 'Error: ' + e.message; 
    $('customResult').classList.remove('hidden'); 
  } finally { 
    $('customBtn').disabled = false; 
    $('customBtn').innerHTML = 'Run diagnosis <span>→</span>'; 
  }
}

async function init() {
  try {
    await api('/api/health'); 
    $('backendStatus').textContent = 'Backend connected'; 
    $('backendStatus').previousElementSibling.style.background = 'var(--accent)';
    const [cases, sum] = await Promise.all([api('/api/cases'), api('/api/summary')]);
    state.cases = cases.cases; 
    renderCases(); 
    renderMetrics(sum.summary);
  } catch(e) { 
    $('backendStatus').textContent = 'Backend offline'; 
  }
}

$('caseSearch').oninput = renderCases; 
$('runBtn').onclick = runDiagnosis; 
$('saveReview').onclick = saveReview; 
$('customBtn').onclick = customDiagnosis; 

init();