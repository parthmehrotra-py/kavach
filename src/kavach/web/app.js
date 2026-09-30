// Kavach UI - Local PII Redaction Workflow

const API_BASE = '/api/v1';

// State
let currentSessionId = null;
let currentCandidates = [];
let currentText = '';
let approvedIds = new Set();

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeUI();
    loadStatus();
    loadCapabilities();
});

function initializeUI() {
    // Accessible text/file tabs
    const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
    tabButtons.forEach((btn, index) => {
        btn.addEventListener('click', () => {
            activateInputTab(btn.dataset.tab);
        });
        btn.addEventListener('keydown', event => {
            if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                event.preventDefault();
                const direction = event.key === 'ArrowRight' ? 1 : -1;
                const nextIndex = (index + direction + tabButtons.length) % tabButtons.length;
                const nextTab = tabButtons[nextIndex];
                activateInputTab(nextTab.dataset.tab);
                nextTab.focus();
            }
        });
    });

    // Event listeners
    document.getElementById('analyze-btn').addEventListener('click', analyzeText);
    document.getElementById('ingest-btn').addEventListener('click', ingestFile);
    document.getElementById('redact-btn').addEventListener('click', redactText);
    document.getElementById('edit-source-btn').addEventListener('click', editSource);
    document.getElementById('cancel-review-btn').addEventListener('click', cancelReview);
    document.getElementById('copy-redacted-btn').addEventListener('click', copyRedacted);
    document.getElementById('new-analysis-btn').addEventListener('click', newAnalysis);
    document.getElementById('restore-btn').addEventListener('click', restoreText);
    document.getElementById('clear-session-btn').addEventListener('click', clearSession);
    document.getElementById('benchmark-btn').addEventListener('click', runBenchmark);
    setWorkflowStep(1);
}

function activateInputTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(button => {
        const selected = button.dataset.tab === tabName;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-selected', String(selected));
    });
    document.querySelectorAll('.tab-content').forEach(panel => {
        const selected = panel.id === `${tabName}-tab`;
        panel.classList.toggle('active', selected);
        panel.hidden = !selected;
    });
}

function setWorkflowStep(step) {
    document.querySelectorAll('.workflow-step').forEach(item => {
        const itemStep = Number(item.dataset.step);
        const current = itemStep === step;
        item.classList.toggle('is-current', current);
        item.classList.toggle('is-complete', itemStep < step);
        if (current) {
            item.setAttribute('aria-current', 'step');
        } else {
            item.removeAttribute('aria-current');
        }
    });
}

async function loadStatus() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        
        const statusEl = document.getElementById('status');
        const statusTextEl = document.getElementById('status-text');
        
        statusEl.className = 'status online';
        statusTextEl.textContent = `Kavach ${data.version} · OCR ${data.ocr_provider} · Contextual ${data.contextual_model_status}`;
    } catch (error) {
        const statusEl = document.getElementById('status');
        const statusTextEl = document.getElementById('status-text');
        statusEl.className = 'status offline';
        statusTextEl.textContent = 'Kavach server unavailable';
    }
}

async function loadCapabilities() {
    try {
        const response = await fetch(`${API_BASE}/hardware/capabilities`);
        const caps = await response.json();
        
        const container = document.getElementById('capabilities-info');
        container.replaceChildren();
        const architectureName = String(caps.architecture);
        const normalizedArchitecture = architectureName.toLowerCase().replace(/[^a-z0-9]/g, '');
        const architecture = normalizedArchitecture.includes('arm')
            ? architectureName
            : normalizedArchitecture.endsWith('64')
                ? 'x64'
                : architectureName;
        const snapdragonStatus = caps.snapdragon_available
            ? 'Available'
            : caps.snapdragon_reason === 'unverified'
                ? 'Unverified on this device'
                : caps.snapdragon_reason;
        const entries = [
            ['Platform', `${caps.platform_name} ${architecture}`],
            ['CPU baseline', caps.cpu_available ? 'Available' : 'Unavailable'],
            ['Snapdragon NPU', snapdragonStatus]
        ];
        entries.forEach(([label, value]) => {
            const item = document.createElement('div');
            item.className = 'capability-item';
            const strong = document.createElement('strong');
            strong.textContent = `${label}: `;
            item.append(strong, document.createTextNode(value));
            container.appendChild(item);
        });
    } catch (error) {
        console.error('Failed to load capabilities:', error);
    }
}

async function analyzeText() {
    const text = document.getElementById('input-text').value.trim();
    if (!text) {
        alert('Please enter some text to analyze');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!response.ok) {
            throw new Error(`Analysis failed: ${response.statusText}`);
        }

        const data = await response.json();
        currentText = text;
        currentCandidates = data.candidates;
        approvedIds.clear();
        
        showReviewSection();
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function ingestFile() {
    const fileInput = document.getElementById('file-input');
    if (!fileInput.files.length) {
        alert('Please select a file');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const response = await fetch(`${API_BASE}/ingest`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Ingestion failed: ${response.statusText}`);
        }

        const data = await response.json();
        
        // Display extracted text
        const display = document.getElementById('extracted-text-display');
        display.textContent = data.extracted_text || '(No text extracted)';
        display.style.display = 'block';
        
        // Use extracted text for analysis
        currentText = data.extracted_text;
        currentCandidates = data.candidates;
        approvedIds.clear();
        
        if (currentCandidates.length > 0) {
            showReviewSection();
        } else {
            alert('No PII candidates detected in extracted text');
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

function showReviewSection() {
    if (currentCandidates.length === 0) {
        alert('No PII candidates detected');
        return;
    }

    // Hide input, show review
    document.getElementById('input-section').style.display = 'none';
    document.getElementById('review-section').style.display = 'block';
    document.getElementById('redacted-section').style.display = 'none';

    renderCandidates();
    setWorkflowStep(2);
}

function renderCandidates() {
    const container = document.getElementById('candidates-list');
    container.replaceChildren();

    currentCandidates.forEach(candidate => {
        const div = document.createElement('div');
        div.className = 'candidate';
        div.dataset.candidateId = candidate.id;

        if (approvedIds.has(candidate.id)) {
            div.classList.add('approved');
        }

        const header = document.createElement('div');
        header.className = 'candidate-header';
        const category = document.createElement('span');
        category.className = 'candidate-category';
        category.textContent = candidate.category;
        const meta = document.createElement('span');
        meta.className = 'candidate-meta';
        meta.textContent = `Confidence: ${(candidate.confidence * 100).toFixed(0)}% • Source: ${candidate.source}`;
        header.append(category, meta);

        const value = document.createElement('div');
        value.className = 'candidate-value masked';
        value.textContent = candidate.value_preview || '***';

        const actions = document.createElement('div');
        actions.className = 'candidate-actions';
        const revealButton = makeButton('Reveal', 'btn btn-secondary', () => {
            revealValue(candidate, value, revealButton);
        });
        const approveButton = makeButton(
            approvedIds.has(candidate.id) ? 'Approved ✓' : 'Approve',
            'btn btn-primary',
            () => approveCandidate(candidate.id)
        );
        const ignoreButton = makeButton('Ignore', 'btn btn-secondary', () => ignoreCandidate(candidate.id));
        actions.append(revealButton, approveButton, ignoreButton);
        div.append(header, value, actions);

        container.appendChild(div);
    });

    updateRedactButton();
}

function makeButton(label, className, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    button.addEventListener('click', onClick);
    return button;
}

function revealValue(candidate, valueEl, button) {
    if (valueEl.classList.contains('masked')) {
        valueEl.classList.remove('masked');
        valueEl.textContent = Array.from(currentText)
            .slice(candidate.start, candidate.end)
            .join('');
        button.textContent = 'Hide';
    } else {
        valueEl.classList.add('masked');
        valueEl.textContent = candidate.value_preview || '***';
        button.textContent = 'Reveal';
    }
}

function approveCandidate(id) {
    const candidateEl = Array.from(document.querySelectorAll('.candidate'))
        .find((element) => element.dataset.candidateId === id);
    if (!candidateEl) return;

    if (approvedIds.has(id)) {
        approvedIds.delete(id);
    } else {
        approvedIds.add(id);
    }

    candidateEl.classList.toggle('approved');
    
    const btn = candidateEl.querySelector('.btn-primary');
    btn.textContent = approvedIds.has(id) ? 'Approved ✓' : 'Approve';
    
    updateRedactButton();
}

function ignoreCandidate(id) {
    const candidateEl = Array.from(document.querySelectorAll('.candidate'))
        .find((element) => element.dataset.candidateId === id);
    if (!candidateEl) return;

    approvedIds.delete(id);
    candidateEl.classList.remove('approved');
    candidateEl.classList.add('ignored');
    candidateEl.style.display = 'none';
    updateRedactButton();
}

function updateRedactButton() {
    const btn = document.getElementById('redact-btn');
    btn.disabled = approvedIds.size === 0;
    if (approvedIds.size === 0) {
        btn.textContent = 'Redact approved details';
        return;
    }
    const noun = approvedIds.size === 1 ? 'detail' : 'details';
    btn.textContent = `Redact ${approvedIds.size} approved ${noun}`;
}

function cancelReview() {
    document.getElementById('input-section').style.display = 'block';
    document.getElementById('review-section').style.display = 'none';
    setWorkflowStep(1);
}

function editSource() {
    const input = document.getElementById('input-text');
    input.value = currentText;
    approvedIds.clear();
    currentCandidates = [];
    document.getElementById('review-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
    activateInputTab('text');
    setWorkflowStep(1);
    input.focus();
}

async function redactText() {
    if (approvedIds.size === 0) {
        alert('Please approve at least one candidate');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/redact`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: currentText,
                approved_candidate_ids: Array.from(approvedIds)
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.message || response.statusText);
        }

        const data = await response.json();
        currentSessionId = data.session_id;

        // Show redacted section
        document.getElementById('review-section').style.display = 'none';
        document.getElementById('redacted-section').style.display = 'block';
        
        document.getElementById('session-id').textContent = currentSessionId;
        document.getElementById('redacted-text').value = data.redacted_text;
        setWorkflowStep(3);
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

function copyRedacted() {
    const textarea = document.getElementById('redacted-text');
    textarea.select();
    document.execCommand('copy');
    
    const btn = document.getElementById('copy-redacted-btn');
    const originalText = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => {
        btn.textContent = originalText;
    }, 2000);
}

async function newAnalysis() {
    if (currentSessionId) {
        if (!confirm('Start a new analysis and delete the current restore session?')) {
            return;
        }
        try {
            await deleteSession(currentSessionId);
            currentSessionId = null;
        } catch (error) {
            alert(`Could not delete the current session: ${error.message}`);
            return;
        }
    }
    resetSensitiveFields();
    document.getElementById('redacted-section').style.display = 'none';
    document.getElementById('input-section').style.display = 'block';
}

async function restoreText() {
    const responseText = document.getElementById('response-text').value.trim();
    if (!responseText) {
        alert('Please paste the AI response');
        return;
    }

    if (!currentSessionId) {
        alert('No active session. Please complete a redaction first.');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                text: responseText
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.message || response.statusText);
        }

        const data = await response.json();
        
        document.getElementById('restored-output').style.display = 'block';
        document.getElementById('restored-text').value = data.restored_text;
        document.getElementById('restore-count').textContent = 
            `✓ Restored ${data.restored_count} placeholder(s)`;
        
        if (data.unresolved_tokens.length > 0) {
            document.getElementById('unresolved-tokens').textContent = 
                `⚠ ${data.unresolved_tokens.length} unresolved token(s): ${data.unresolved_tokens.join(', ')}`;
        } else {
            document.getElementById('unresolved-tokens').textContent = '';
        }
        setWorkflowStep(4);
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function clearSession() {
    if (!confirm('Clear session and reset all fields? This cannot be undone.')) {
        return;
    }

    let deleted = !currentSessionId;
    if (currentSessionId) {
        try {
            await deleteSession(currentSessionId);
            currentSessionId = null;
            deleted = true;
        } catch (error) {
            console.error('Failed to delete session:', error);
        }
    }

    resetSensitiveFields();

    if (deleted) {
        alert('Session cleared and fields reset');
    } else {
        alert('Local fields were cleared, but server deletion failed. Keep Kavach open and use Clear again to retry.');
    }
}

async function deleteSession(sessionId) {
    const response = await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}`, {
        method: 'DELETE'
    });
    if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
    }
}

function resetSensitiveFields() {
    currentCandidates = [];
    currentText = '';
    approvedIds.clear();

    // Clear all sensitive fields
    document.getElementById('input-text').value = '';
    document.getElementById('file-input').value = '';
    document.getElementById('extracted-text-display').textContent = '';
    document.getElementById('extracted-text-display').style.display = 'none';
    document.getElementById('candidates-list').replaceChildren();
    document.getElementById('redacted-text').value = '';
    document.getElementById('session-id').textContent = '';
    document.getElementById('response-text').value = '';
    document.getElementById('restored-text').value = '';
    document.getElementById('restore-count').textContent = '';
    document.getElementById('unresolved-tokens').textContent = '';

    // Reset UI
    document.getElementById('input-section').style.display = 'block';
    document.getElementById('review-section').style.display = 'none';
    document.getElementById('redacted-section').style.display = 'none';
    document.getElementById('restored-output').style.display = 'none';
    setWorkflowStep(1);
}

async function runBenchmark() {
    const btn = document.getElementById('benchmark-btn');
    btn.disabled = true;
    btn.textContent = 'Running...';

    try {
        const response = await fetch(`${API_BASE}/benchmark`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repetitions: 10 })
        });

        if (!response.ok) {
            throw new Error(`Benchmark failed: ${response.statusText}`);
        }

        const data = await response.json();
        
        const resultDiv = document.getElementById('benchmark-result');
        resultDiv.style.display = 'block';
        resultDiv.className = 'benchmark-result';
        resultDiv.replaceChildren();
        const title = document.createElement('strong');
        title.textContent = 'Benchmark Results:';
        resultDiv.appendChild(title);
        const details = [
            `Method: ${data.method}`,
            `Workload: ${data.workload_description}`,
            `Provider: ${data.provider}`,
            `Runtime: ${data.runtime}`,
            `Device: ${data.device_label.split(/\s+/).map((part) => {
                const normalizedPart = part.toLowerCase().replace(/[^a-z0-9]/g, '');
                return normalizedPart.endsWith('64') && !normalizedPart.startsWith('arm')
                    ? 'x64'
                    : part;
            }).join(' ')}`,
            `Elapsed: ${data.elapsed_seconds.toFixed(3)}s`
        ];
        if (data.throughput_items_per_sec) {
            details.push(`Throughput: ${data.throughput_items_per_sec.toFixed(1)} items/sec`);
        }
        details.forEach(detail => {
            const line = document.createElement('div');
            line.textContent = detail;
            resultDiv.appendChild(line);
        });
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run Benchmark';
    }
}
