// apostas.js — Aba Minhas Apostas

let _allBets = [];
let _printModalOpen = false;
let _editingBetId = null;

// Global paste listener — captures Ctrl+V when print modal is open
document.addEventListener('paste', (e) => {
  if (!_printModalOpen) return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) { importarPrintFile(file); return; }
    }
  }
});

async function loadApostas() {
  const container = document.getElementById('tab-apostas');
  const shellExists = !!document.getElementById('betList');

  if (!shellExists) {
    container.innerHTML = '<div style="padding:60px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px;letter-spacing:0.08em">Carregando...</div>';
  }

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    _allBets = await res.json();
    if (!document.getElementById('betList')) setupApostasShell();
    renderApostas();
  } catch (e) {
    container.innerHTML = `<div style="padding:60px;text-align:center;color:var(--red);font-family:var(--font-mono);font-size:12px">${e.message}</div>`;
  }
}

function setupApostasShell() {
  const container = document.getElementById('tab-apostas');
  container.innerHTML = `
    <div class="pg-wrap">

      <!-- Header -->
      <div class="pg-hdr">
        <div>
          <h1 class="section-title">APOSTAS</h1>
          <div class="section-sub">Histórico e gestão</div>
        </div>
        <div class="hdr-actions">
          <button class="btn-primary" onclick="abrirFormulario()">+ Nova</button>
          <label class="btn-outline" style="cursor:pointer">
            ↑ CSV
            <input type="file" accept=".csv" style="display:none" onchange="importarCSV(this)" />
          </label>
          <button class="btn-outline" onclick="abrirPrintModal()">◈ Print IA</button>
        </div>
      </div>

      <!-- Filters -->
      <div class="filters-row">
        <input class="f-input" style="flex:1;min-width:160px" id="filtroTexto"
               placeholder="Buscar partida ou descrição…" oninput="renderApostas()" />
        <select class="f-input" id="filtroResultado" onchange="renderApostas()">
          <option value="todos">Todos</option>
          <option value="ganhou">Ganhou</option>
          <option value="perdeu">Perdeu</option>
          <option value="pendente">Pendente</option>
          <option value="void">Void</option>
        </select>
        <input type="date" class="f-input" id="filtroDe"  onchange="renderApostas()" />
        <input type="date" class="f-input" id="filtroAte" onchange="renderApostas()" />
      </div>

      <!-- Bet list (updated by renderApostas) -->
      <div id="betList"></div>

    </div>

    <!-- ── Print import modal ── -->
    <div id="printModalOverlay"
         style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:300;
                backdrop-filter:blur(6px);align-items:center;justify-content:center"
         onclick="fecharPrintModal()">
      <div onclick="event.stopPropagation()"
           style="background:var(--surface);border:1px solid var(--border);border-radius:14px;
                  width:100%;max-width:480px;padding:32px;margin:24px;
                  box-shadow:0 28px 80px rgba(0,0,0,0.6);animation:slideIn 0.2s ease">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
          <span style="font-family:var(--font-brand);font-weight:800;font-size:17px;letter-spacing:0.05em">
            IMPORTAR POR PRINT
          </span>
          <button class="btn-close" onclick="fecharPrintModal()">×</button>
        </div>
        <div id="pasteZone" tabindex="0" onclick="this.focus()"
             style="border:2px dashed var(--border);border-radius:10px;padding:40px 24px;
                    text-align:center;cursor:pointer;transition:border-color 0.15s,background 0.15s;
                    outline:none;position:relative"
             onfocus="this.style.borderColor='rgba(198,241,53,0.5)';this.style.background='rgba(198,241,53,0.03)'"
             onblur="this.style.borderColor='var(--border)';this.style.background=''">
          <div style="font-size:32px;margin-bottom:12px;opacity:0.5">📋</div>
          <div style="font-family:var(--font-brand);font-weight:700;font-size:15px;letter-spacing:0.05em;color:var(--text)">
            Ctrl+V para colar screenshot
          </div>
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--muted);margin-top:6px;letter-spacing:0.06em">
            Clique aqui, depois cole a imagem
          </div>
          <div id="pastePreview" style="margin-top:16px;display:none">
            <img id="pastePreviewImg"
                 style="max-width:100%;max-height:160px;border-radius:6px;border:1px solid var(--border)" />
            <div style="font-family:var(--font-mono);font-size:10px;color:var(--green);margin-top:8px;
                        letter-spacing:0.06em" id="pastePreviewLabel">Imagem capturada ✓</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:12px;margin:18px 0">
          <div style="flex:1;height:1px;background:var(--border)"></div>
          <span style="font-family:var(--font-mono);font-size:10px;color:var(--muted);letter-spacing:0.1em">OU</span>
          <div style="flex:1;height:1px;background:var(--border)"></div>
        </div>
        <label style="display:flex;align-items:center;justify-content:center;gap:8px;padding:11px;
                      border:1px solid var(--border);border-radius:8px;cursor:pointer;
                      transition:border-color 0.15s,background 0.15s;font-size:13px;
                      font-weight:600;color:var(--soft)"
               onmouseover="this.style.borderColor='rgba(255,255,255,0.15)';this.style.background='rgba(255,255,255,0.03)'"
               onmouseout="this.style.borderColor='var(--border)';this.style.background=''">
          ↑ Escolher arquivo
          <input type="file" accept="image/*" style="display:none" onchange="importarPrintFromInput(this)" />
        </label>
        <div id="printStatus"
             style="margin-top:16px;min-height:18px;text-align:center;font-family:var(--font-mono);
                    font-size:11px;color:var(--muted);letter-spacing:0.06em"></div>
      </div>
    </div>

    <!-- ── Form panel overlay ── -->
    <div id="formOverlay"
         style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);
                z-index:198;backdrop-filter:blur(4px)"
         onclick="fecharFormulario()"></div>

    <!-- ── Form panel ── -->
    <div id="formPanel"
         style="display:none;position:fixed;top:0;right:0;bottom:0;width:400px;max-width:100vw;
                background:var(--surface);border-left:1px solid var(--border);overflow-y:auto;
                z-index:199;flex-direction:column;box-shadow:-20px 0 60px rgba(0,0,0,0.45)">
      <div class="fp-hdr">
        <span class="fp-title" id="fpTitle">NOVA APOSTA</span>
        <button class="btn-close" onclick="fecharFormulario()">×</button>
      </div>
      <div class="fp-body">
        <label class="fp-label">Partida</label>
        <input class="fp-input" type="text" id="formPartida" placeholder="Lakers vs Celtics" />

        <label class="fp-label">Descrição</label>
        <input class="fp-input" type="text" id="formDescricao" placeholder="LeBron Mais de 25.5" />

        <label class="fp-label">Tipo</label>
        <select class="fp-input" id="formTipo">
          <option>Vencedor</option>
          <option>Handicap</option>
          <option>Totais</option>
          <option>Jogador</option>
          <option>Outro</option>
        </select>

        <div class="fp-row">
          <div>
            <label class="fp-label">Odds</label>
            <input class="fp-input" type="number" step="0.01" id="formOdds" placeholder="1.85" />
          </div>
          <div>
            <label class="fp-label">Stake (R$)</label>
            <input class="fp-input" type="number" step="0.01" id="formStake" placeholder="50" />
          </div>
        </div>

        <label class="fp-label">Data</label>
        <input class="fp-input" type="date" id="formData" />

        <label class="fp-label">Resultado</label>
        <select class="fp-input" id="formResultado" onchange="toggleLucroField()">
          <option value="pendente">Pendente</option>
          <option value="ganhou">Ganhou</option>
          <option value="perdeu">Perdeu</option>
          <option value="void">Void</option>
        </select>

        <div id="lucroFieldWrap" style="display:none;">
          <label class="fp-label">Lucro/Prejuízo (R$)</label>
          <input class="fp-input" type="number" step="0.01" id="formLucro" placeholder="Vazio = cálculo automático" />
          <div style="font-size:0.7rem;color:var(--muted);margin-top:4px;">
            Deixe vazio para calcular com base em odds × stake. Preencha para múltiplas ou cashout.
          </div>
        </div>
      </div>
      <div class="fp-footer">
        <button class="btn-danger" id="btnExcluir" style="display:none" onclick="excluirAposta()">
          🗑 Excluir
        </button>
        <button class="btn-outline" onclick="fecharFormulario()" style="flex:1">Cancelar</button>
        <button class="btn-primary" id="btnSalvar" onclick="salvarAposta()" style="flex:2">
          Salvar Aposta
        </button>
      </div>
    </div>`;
}

function renderApostas() {
  const betList = document.getElementById('betList');
  if (!betList) return;

  const q   = (document.getElementById('filtroTexto')?.value    || '').toLowerCase();
  const res = (document.getElementById('filtroResultado')?.value || 'todos');
  const de  =  document.getElementById('filtroDe')?.value  || '';
  const ate =  document.getElementById('filtroAte')?.value || '';

  if (_allBets.length === 0) {
    betList.innerHTML = `
      <div style="text-align:center;padding:80px 24px">
        <div style="font-size:44px;margin-bottom:16px;opacity:0.4">◎</div>
        <p style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;line-height:1.8">
          NENHUMA APOSTA REGISTRADA<br>Importe ou adicione manualmente.
        </p>
      </div>`;
    return;
  }

  let bets = [..._allBets].sort((a, b) => b.data.localeCompare(a.data));
  if (q)               bets = bets.filter(b => b.partida?.toLowerCase().includes(q) || b.descricao?.toLowerCase().includes(q));
  if (res !== 'todos') bets = bets.filter(b => b.resultado === res);
  if (de)              bets = bets.filter(b => b.data >= de);
  if (ate)             bets = bets.filter(b => b.data <= ate);

  betList.innerHTML = bets.length === 0
    ? `<div style="text-align:center;padding:60px 24px;color:var(--muted);font-family:var(--font-mono);font-size:11px;letter-spacing:0.08em">
         Nenhuma aposta encontrada.
       </div>`
    : `<div class="bet-list">${bets.map(buildBetCard).join('')}</div>`;
}

// ── Bet card builder ─────────────────────────────────────────────────────
function buildBetCard(b) {
  const BADGE = {
    ganhou:   '<span class="b-badge b-win">↑ Ganhou</span>',
    perdeu:   '<span class="b-badge b-loss">↓ Perdeu</span>',
    pendente: '<span class="b-badge b-pend">Pendente</span>',
    void:     '<span class="b-badge b-void">Void</span>',
  };

  const pnlClass = b.lucro_prejuizo == null ? 't-pnl-zero'
                 : b.lucro_prejuizo >= 0    ? 't-pnl-pos' : 't-pnl-neg';
  const pnlArrow = b.lucro_prejuizo == null ? ''
                 : b.lucro_prejuizo >= 0    ? '↑ ' : '↓ ';
  const pnlText  = b.lucro_prejuizo == null ? '—'
                 : pnlArrow + 'R$ ' + Math.abs(b.lucro_prejuizo).toFixed(2);

  return `
    <div class="bet-card bc-${escH(b.resultado)}">
      <div class="bc-accent"></div>
      <div class="bc-content">
        <div class="bc-row1">
          <span class="bc-match">${escH(b.partida)}</span>
          ${BADGE[b.resultado] ?? `<span class="b-badge b-void">${escH(b.resultado)}</span>`}
        </div>
        <div class="bc-desc" title="${escH(b.descricao)}">${escH(b.descricao) || '—'}</div>
        <div class="bc-row3">
          <div class="bc-chips">
            <span class="bc-chip">${escH(b.tipo_aposta || 'Outro')}</span>
            <span class="bc-chip">@ ${b.odds?.toFixed(2) ?? '—'}</span>
            <span class="bc-chip">R$ ${b.stake?.toFixed(2) ?? '—'}</span>
            <span class="bc-chip">${escH(b.data)}</span>
          </div>
          <div class="bc-right">
            <span class="bc-pnl ${pnlClass}">${pnlText}</span>
            <button class="bc-edit" onclick="editarAposta('${escH(b.bet_id)}')">✎</button>
          </div>
        </div>
      </div>
    </div>`;
}

// ── Form panel controls ──────────────────────────────────────────────────
function abrirFormulario() {
  _editingBetId = null;
  const title = document.getElementById('fpTitle');
  if (title) title.textContent = 'NOVA APOSTA';
  const btnEx = document.getElementById('btnExcluir');
  if (btnEx) btnEx.style.display = 'none';
  const btnSv = document.getElementById('btnSalvar');
  if (btnSv) btnSv.textContent = 'Salvar Aposta';

  // Reset fields
  ['formPartida', 'formDescricao', 'formOdds', 'formStake', 'formLucro'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const lucroWrap = document.getElementById('lucroFieldWrap');
  if (lucroWrap) lucroWrap.style.display = 'none';
  const tipo = document.getElementById('formTipo');
  if (tipo) tipo.value = 'Vencedor';
  const result = document.getElementById('formResultado');
  if (result) result.value = 'pendente';
  const data = document.getElementById('formData');
  if (data) data.value = new Date().toISOString().slice(0, 10);

  document.getElementById('formPanel').style.display = 'flex';
  document.getElementById('formOverlay').style.display = 'block';
}

function editarAposta(betId) {
  const bet = _allBets.find(b => b.bet_id === betId);
  if (!bet) return;

  _editingBetId = betId;
  const title = document.getElementById('fpTitle');
  if (title) title.textContent = 'EDITAR APOSTA';
  const btnEx = document.getElementById('btnExcluir');
  if (btnEx) btnEx.style.display = 'block';
  const btnSv = document.getElementById('btnSalvar');
  if (btnSv) btnSv.textContent = 'Salvar Alterações';

  // Fill fields
  document.getElementById('formPartida').value  = bet.partida   || '';
  document.getElementById('formDescricao').value = bet.descricao || '';
  document.getElementById('formTipo').value       = bet.tipo_aposta || 'Outro';
  document.getElementById('formOdds').value       = bet.odds  ?? '';
  document.getElementById('formStake').value      = bet.stake ?? '';
  document.getElementById('formData').value       = bet.data  || '';
  document.getElementById('formResultado').value  = bet.resultado || 'pendente';
  document.getElementById('formLucro').value      = bet.lucro_prejuizo ?? '';
  toggleLucroField();

  document.getElementById('formPanel').style.display = 'flex';
  document.getElementById('formOverlay').style.display = 'block';
}

function toggleLucroField() {
  const resultado = document.getElementById('formResultado').value;
  const wrap = document.getElementById('lucroFieldWrap');
  if (wrap) wrap.style.display = resultado !== 'pendente' ? 'block' : 'none';
}

function fecharFormulario() {
  _editingBetId = null;
  document.getElementById('formPanel').style.display   = 'none';
  document.getElementById('formOverlay').style.display = 'none';
}

// ── Save (create or update) ───────────────────────────────────────────────
async function salvarAposta() {
  const lucroVal = document.getElementById('formLucro').value.trim();
  const body = {
    partida:     document.getElementById('formPartida').value,
    descricao:   document.getElementById('formDescricao').value,
    tipo_aposta: document.getElementById('formTipo').value,
    odds:        parseFloat(document.getElementById('formOdds').value),
    stake:       parseFloat(document.getElementById('formStake').value),
    data:        document.getElementById('formData').value,
    resultado:   document.getElementById('formResultado').value,
  };
  if (lucroVal !== '') body.lucro_prejuizo = parseFloat(lucroVal);

  const url    = _editingBetId ? `/api/bets/${_editingBetId}` : '/api/bets';
  const method = _editingBetId ? 'PUT' : 'POST';

  const res = await authFetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (res.ok) {
    const bet = await res.json();
    if (_editingBetId) {
      const idx = _allBets.findIndex(b => b.bet_id === _editingBetId);
      if (idx !== -1) _allBets[idx] = bet; else _allBets.unshift(bet);
    } else {
      _allBets.unshift(bet);
    }
    const msg = _editingBetId ? '✅ Aposta atualizada!' : '✅ Aposta adicionada!';
    fecharFormulario();
    renderApostas();
    showToast(msg);
  } else {
    showToast('❌ Erro ao salvar aposta');
  }
}

// ── Delete ────────────────────────────────────────────────────────────────
async function excluirAposta() {
  if (!_editingBetId) return;
  if (!confirm('Excluir esta aposta? Esta ação não pode ser desfeita.')) return;

  const res = await authFetch(`/api/bets/${_editingBetId}`, { method: 'DELETE' });
  if (res.ok || res.status === 204) {
    _allBets = _allBets.filter(b => b.bet_id !== _editingBetId);
    fecharFormulario();
    renderApostas();
    showToast('🗑 Aposta excluída');
  } else {
    showToast('❌ Erro ao excluir aposta');
  }
}

// ── Print / CSV import ────────────────────────────────────────────────────
function abrirPrintModal() {
  const modal = document.getElementById('printModalOverlay');
  if (!modal) return;
  modal.style.display = 'flex';
  _printModalOpen = true;
  setTimeout(() => document.getElementById('pasteZone')?.focus(), 60);
}

function fecharPrintModal() {
  const modal = document.getElementById('printModalOverlay');
  if (!modal) return;
  modal.style.display = 'none';
  _printModalOpen = false;
  const preview = document.getElementById('pastePreview');
  if (preview) preview.style.display = 'none';
  const status = document.getElementById('printStatus');
  if (status) status.textContent = '';
}

async function importarPrintFile(file) {
  const status = document.getElementById('printStatus');
  const preview = document.getElementById('pastePreview');
  const previewImg = document.getElementById('pastePreviewImg');
  if (preview && previewImg) {
    previewImg.src = URL.createObjectURL(file);
    preview.style.display = 'block';
  }
  if (status) status.textContent = 'Analisando com IA...';

  const form = new FormData();
  form.append('file', file);
  const res = await authFetch('/api/bets/import-screenshot', { method: 'POST', body: form });
  if (res.ok) {
    const data = await res.json();
    fecharPrintModal();
    showToast(`✅ ${data.importadas} apostas importadas, ${data.ignoradas} ignoradas`);
    await loadApostas();
  } else {
    const err = await res.json().catch(() => ({}));
    if (status) status.textContent = '❌ ' + (err.detail || 'Erro ao importar print');
  }
}

function importarPrintFromInput(input) {
  const file = input.files[0];
  if (file) importarPrintFile(file);
  input.value = '';
}

async function importarCSV(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  showToast('⏳ Importando...');
  const res = await authFetch('/api/bets/import', { method: 'POST', body: form });
  if (res.ok) {
    const data = await res.json();
    showToast(`✅ ${data.importadas} apostas importadas, ${data.ignoradas} ignoradas`);
    await loadApostas();
  } else {
    showToast('❌ Erro ao importar CSV');
  }
  input.value = '';
}

function escH(str) {
  return String(str ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
