// diversas.js — Aba Apostas Diversas (não-NBA)
// Espelha apostas.js, mas usa a coleção/endpoint /api/bets-diversas e adiciona o campo Esporte.
// Todos os ids/funções têm sufixo "Dv" para não colidir com a aba Apostas (ambos shells vivem no DOM).
// Reaproveita escH() (apostas.js) e showToast() (index.html), carregados antes deste arquivo.

let _allDiversas = [];
let _printModalOpenDv = false;
let _editingDiversaId = null;

const ESPORTES_DV = ['Futebol', 'Tênis', 'Basquete', 'eSports', 'Vôlei', 'MMA', 'Corrida', 'Outro'];
const MERCADOS_DV  = ['Vencedor', 'Dupla Chance', 'Handicap', 'Totais', 'Ambas Marcam', 'Escanteios', 'Cartões', 'Outro'];

// Global paste listener — captura Ctrl+V quando o modal de print está aberto
document.addEventListener('paste', (e) => {
  if (!_printModalOpenDv) return;
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile();
      if (file) { importarPrintFileDv(file); return; }
    }
  }
});

async function loadDiversas() {
  const container = document.getElementById('tab-diversas');
  const shellExists = !!document.getElementById('betListDv');

  if (!shellExists) {
    container.innerHTML = '<div style="padding:60px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px;letter-spacing:0.08em">Carregando...</div>';
  }

  try {
    const res = await authFetch('/api/bets-diversas');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    _allDiversas = await res.json();
    if (!document.getElementById('betListDv')) setupDiversasShell();
    renderDiversas();
  } catch (e) {
    container.innerHTML = `<div style="padding:60px;text-align:center;color:var(--red);font-family:var(--font-mono);font-size:12px">${e.message}</div>`;
  }
}

function setupDiversasShell() {
  const container = document.getElementById('tab-diversas');
  container.innerHTML = `
    <div class="pg-wrap">

      <!-- Header -->
      <div class="pg-hdr">
        <div>
          <h1 class="section-title">DIVERSAS</h1>
          <div class="section-sub">Apostas fora da NBA · histórico e gestão</div>
        </div>
        <div class="hdr-actions">
          <button class="btn-primary" onclick="abrirFormularioDv()">+ Nova</button>
          <label class="btn-outline" style="cursor:pointer">
            ↑ CSV
            <input type="file" accept=".csv" style="display:none" onchange="importarCSVDv(this)" />
          </label>
          <button class="btn-outline" onclick="abrirPrintModalDv()">◈ Print IA</button>
        </div>
      </div>

      <!-- Filters -->
      <div class="filters-row">
        <input class="f-input" style="flex:1;min-width:160px" id="filtroTextoDv"
               placeholder="Buscar partida ou descrição…" oninput="renderDiversas()" />
        <select class="f-input" id="filtroEsporteDv" onchange="renderDiversas()">
          <option value="todos">Esporte: todos</option>
          ${ESPORTES_DV.map(e => `<option value="${escH(e)}">${escH(e)}</option>`).join('')}
        </select>
        <select class="f-input" id="filtroResultadoDv" onchange="renderDiversas()">
          <option value="todos">Todos</option>
          <option value="ganhou">Ganhou</option>
          <option value="perdeu">Perdeu</option>
          <option value="pendente">Pendente</option>
          <option value="void">Void</option>
        </select>
        <input type="date" class="f-input" id="filtroDeDv"  onchange="renderDiversas()" />
        <input type="date" class="f-input" id="filtroAteDv" onchange="renderDiversas()" />
      </div>

      <!-- Bet list (updated by renderDiversas) -->
      <div id="betListDv"></div>

    </div>

    <!-- ── Print import modal ── -->
    <div id="printModalOverlayDv"
         style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:300;
                backdrop-filter:blur(6px);align-items:center;justify-content:center"
         onclick="fecharPrintModalDv()">
      <div onclick="event.stopPropagation()"
           style="background:var(--surface);border:1px solid var(--border);border-radius:14px;
                  width:100%;max-width:480px;padding:32px;margin:24px;
                  box-shadow:0 28px 80px rgba(0,0,0,0.6);animation:slideIn 0.2s ease">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
          <span style="font-family:var(--font-brand);font-weight:800;font-size:17px;letter-spacing:0.05em">
            IMPORTAR POR PRINT
          </span>
          <button class="btn-close" onclick="fecharPrintModalDv()">×</button>
        </div>
        <div id="pasteZoneDv" tabindex="0" onclick="this.focus()"
             style="border:2px dashed var(--border);border-radius:10px;padding:40px 24px;
                    text-align:center;cursor:pointer;transition:border-color 0.15s,background 0.15s;
                    outline:none;position:relative"
             onfocus="this.style.borderColor='rgba(245,158,11,0.5)';this.style.background='rgba(245,158,11,0.03)'"
             onblur="this.style.borderColor='var(--border)';this.style.background=''">
          <div style="font-size:32px;margin-bottom:12px;opacity:0.5">📋</div>
          <div style="font-family:var(--font-brand);font-weight:700;font-size:15px;letter-spacing:0.05em;color:var(--text)">
            Ctrl+V para colar screenshot
          </div>
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--muted);margin-top:6px;letter-spacing:0.06em">
            Clique aqui, depois cole a imagem
          </div>
          <div id="pastePreviewDv" style="margin-top:16px;display:none">
            <img id="pastePreviewImgDv"
                 style="max-width:100%;max-height:160px;border-radius:6px;border:1px solid var(--border)" />
            <div style="font-family:var(--font-mono);font-size:10px;color:var(--green);margin-top:8px;
                        letter-spacing:0.06em">Imagem capturada ✓</div>
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
          <input type="file" accept="image/*" style="display:none" onchange="importarPrintFromInputDv(this)" />
        </label>
        <div id="printStatusDv"
             style="margin-top:16px;min-height:18px;text-align:center;font-family:var(--font-mono);
                    font-size:11px;color:var(--muted);letter-spacing:0.06em"></div>
      </div>
    </div>

    <!-- ── Form panel overlay ── -->
    <div id="formOverlayDv"
         style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);
                z-index:198;backdrop-filter:blur(4px)"
         onclick="fecharFormularioDv()"></div>

    <!-- ── Form panel ── -->
    <div id="formPanelDv"
         style="display:none;position:fixed;top:0;right:0;bottom:0;width:400px;max-width:100vw;
                background:var(--surface);border-left:1px solid var(--border);overflow-y:auto;
                z-index:199;flex-direction:column;box-shadow:-20px 0 60px rgba(0,0,0,0.45)">
      <div class="fp-hdr">
        <span class="fp-title" id="fpTitleDv">NOVA APOSTA</span>
        <button class="btn-close" onclick="fecharFormularioDv()">×</button>
      </div>
      <div class="fp-body">
        <label class="fp-label">Partida / Evento</label>
        <input class="fp-input" type="text" id="formPartidaDv" placeholder="Flamengo vs Palmeiras" />

        <label class="fp-label">Descrição</label>
        <input class="fp-input" type="text" id="formDescricaoDv" placeholder="Flamengo vence" />

        <div class="fp-row">
          <div>
            <label class="fp-label">Esporte</label>
            <select class="fp-input" id="formEsporteDv">
              ${ESPORTES_DV.map(e => `<option>${escH(e)}</option>`).join('')}
            </select>
          </div>
          <div>
            <label class="fp-label">Mercado</label>
            <select class="fp-input" id="formTipoDv">
              ${MERCADOS_DV.map(m => `<option>${escH(m)}</option>`).join('')}
            </select>
          </div>
        </div>

        <div class="fp-row">
          <div>
            <label class="fp-label">Odds</label>
            <input class="fp-input" type="number" step="0.01" id="formOddsDv" placeholder="1.85" />
          </div>
          <div>
            <label class="fp-label">Stake (R$)</label>
            <input class="fp-input" type="number" step="0.01" id="formStakeDv" placeholder="50" />
          </div>
        </div>

        <label class="fp-label">Data</label>
        <input class="fp-input" type="date" id="formDataDv" />

        <label class="fp-label">Resultado</label>
        <select class="fp-input" id="formResultadoDv" onchange="toggleLucroFieldDv()">
          <option value="pendente">Pendente</option>
          <option value="ganhou">Ganhou</option>
          <option value="perdeu">Perdeu</option>
          <option value="void">Void</option>
        </select>

        <div id="lucroFieldWrapDv" style="display:none;">
          <label class="fp-label">Lucro/Prejuízo (R$)</label>
          <input class="fp-input" type="number" step="0.01" id="formLucroDv" placeholder="Vazio = cálculo automático" />
          <div style="font-size:0.7rem;color:var(--muted);margin-top:4px;">
            Deixe vazio para calcular com base em odds × stake. Preencha para múltiplas ou cashout.
          </div>
        </div>
      </div>
      <div class="fp-footer">
        <button class="btn-danger" id="btnExcluirDv" style="display:none" onclick="excluirDiversa()">
          🗑 Excluir
        </button>
        <button class="btn-outline" onclick="fecharFormularioDv()" style="flex:1">Cancelar</button>
        <button class="btn-primary" id="btnSalvarDv" onclick="salvarDiversa()" style="flex:2">
          Salvar Aposta
        </button>
      </div>
    </div>`;
}

function renderDiversas() {
  const betList = document.getElementById('betListDv');
  if (!betList) return;

  const q   = (document.getElementById('filtroTextoDv')?.value     || '').toLowerCase();
  const esp = (document.getElementById('filtroEsporteDv')?.value   || 'todos');
  const res = (document.getElementById('filtroResultadoDv')?.value || 'todos');
  const de  =  document.getElementById('filtroDeDv')?.value  || '';
  const ate =  document.getElementById('filtroAteDv')?.value || '';

  if (_allDiversas.length === 0) {
    betList.innerHTML = `
      <div style="text-align:center;padding:80px 24px">
        <div style="font-size:44px;margin-bottom:16px;opacity:0.4">◎</div>
        <p style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;line-height:1.8">
          NENHUMA APOSTA REGISTRADA<br>Importe ou adicione manualmente.
        </p>
      </div>`;
    return;
  }

  let bets = [..._allDiversas].sort((a, b) => b.data.localeCompare(a.data));
  if (q)               bets = bets.filter(b => b.partida?.toLowerCase().includes(q) || b.descricao?.toLowerCase().includes(q));
  if (esp !== 'todos') bets = bets.filter(b => (b.esporte || 'Outro') === esp);
  if (res !== 'todos') bets = bets.filter(b => b.resultado === res);
  if (de)              bets = bets.filter(b => b.data >= de);
  if (ate)             bets = bets.filter(b => b.data <= ate);

  betList.innerHTML = bets.length === 0
    ? `<div style="text-align:center;padding:60px 24px;color:var(--muted);font-family:var(--font-mono);font-size:11px;letter-spacing:0.08em">
         Nenhuma aposta encontrada.
       </div>`
    : `<div class="bet-list">${bets.map(buildDiversaCard).join('')}</div>`;
}

// ── Bet card builder ─────────────────────────────────────────────────────
function buildDiversaCard(b) {
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
            <span class="bc-chip">${escH(b.esporte || 'Outro')}</span>
            <span class="bc-chip">${escH(b.tipo_aposta || 'Outro')}</span>
            <span class="bc-chip">@ ${b.odds?.toFixed(2) ?? '—'}</span>
            <span class="bc-chip">R$ ${b.stake?.toFixed(2) ?? '—'}</span>
            <span class="bc-chip">${escH(b.data)}</span>
          </div>
          <div class="bc-right">
            <span class="bc-pnl ${pnlClass}">${pnlText}</span>
            <button class="bc-edit" onclick="editarDiversa('${escH(b.bet_id)}')">✎</button>
          </div>
        </div>
      </div>
    </div>`;
}

// ── Form panel controls ──────────────────────────────────────────────────
function abrirFormularioDv() {
  _editingDiversaId = null;
  const title = document.getElementById('fpTitleDv');
  if (title) title.textContent = 'NOVA APOSTA';
  const btnEx = document.getElementById('btnExcluirDv');
  if (btnEx) btnEx.style.display = 'none';
  const btnSv = document.getElementById('btnSalvarDv');
  if (btnSv) btnSv.textContent = 'Salvar Aposta';

  // Reset fields
  ['formPartidaDv', 'formDescricaoDv', 'formOddsDv', 'formStakeDv', 'formLucroDv'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const lucroWrap = document.getElementById('lucroFieldWrapDv');
  if (lucroWrap) lucroWrap.style.display = 'none';
  const esp = document.getElementById('formEsporteDv');
  if (esp) esp.value = 'Futebol';
  const tipo = document.getElementById('formTipoDv');
  if (tipo) tipo.value = 'Vencedor';
  const result = document.getElementById('formResultadoDv');
  if (result) result.value = 'pendente';
  const data = document.getElementById('formDataDv');
  if (data) data.value = new Date().toISOString().slice(0, 10);

  document.getElementById('formPanelDv').style.display = 'flex';
  document.getElementById('formOverlayDv').style.display = 'block';
}

function editarDiversa(betId) {
  const bet = _allDiversas.find(b => b.bet_id === betId);
  if (!bet) return;

  _editingDiversaId = betId;
  const title = document.getElementById('fpTitleDv');
  if (title) title.textContent = 'EDITAR APOSTA';
  const btnEx = document.getElementById('btnExcluirDv');
  if (btnEx) btnEx.style.display = 'block';
  const btnSv = document.getElementById('btnSalvarDv');
  if (btnSv) btnSv.textContent = 'Salvar Alterações';

  // Fill fields
  document.getElementById('formPartidaDv').value   = bet.partida   || '';
  document.getElementById('formDescricaoDv').value = bet.descricao || '';
  document.getElementById('formEsporteDv').value   = bet.esporte || 'Outro';
  document.getElementById('formTipoDv').value      = bet.tipo_aposta || 'Outro';
  document.getElementById('formOddsDv').value      = bet.odds  ?? '';
  document.getElementById('formStakeDv').value     = bet.stake ?? '';
  document.getElementById('formDataDv').value      = bet.data  || '';
  document.getElementById('formResultadoDv').value = bet.resultado || 'pendente';
  document.getElementById('formLucroDv').value     = bet.lucro_prejuizo ?? '';
  toggleLucroFieldDv();

  document.getElementById('formPanelDv').style.display = 'flex';
  document.getElementById('formOverlayDv').style.display = 'block';
}

function toggleLucroFieldDv() {
  const resultado = document.getElementById('formResultadoDv').value;
  const wrap = document.getElementById('lucroFieldWrapDv');
  if (wrap) wrap.style.display = resultado !== 'pendente' ? 'block' : 'none';
}

function fecharFormularioDv() {
  _editingDiversaId = null;
  document.getElementById('formPanelDv').style.display   = 'none';
  document.getElementById('formOverlayDv').style.display = 'none';
}

// ── Save (create or update) ───────────────────────────────────────────────
async function salvarDiversa() {
  const lucroVal = document.getElementById('formLucroDv').value.trim();
  const body = {
    partida:     document.getElementById('formPartidaDv').value,
    descricao:   document.getElementById('formDescricaoDv').value,
    esporte:     document.getElementById('formEsporteDv').value,
    tipo_aposta: document.getElementById('formTipoDv').value,
    odds:        parseFloat(document.getElementById('formOddsDv').value),
    stake:       parseFloat(document.getElementById('formStakeDv').value),
    data:        document.getElementById('formDataDv').value,
    resultado:   document.getElementById('formResultadoDv').value,
  };
  if (lucroVal !== '') body.lucro_prejuizo = parseFloat(lucroVal);

  const url    = _editingDiversaId ? `/api/bets-diversas/${_editingDiversaId}` : '/api/bets-diversas';
  const method = _editingDiversaId ? 'PUT' : 'POST';

  const res = await authFetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (res.ok) {
    const bet = await res.json();
    if (_editingDiversaId) {
      const idx = _allDiversas.findIndex(b => b.bet_id === _editingDiversaId);
      if (idx !== -1) _allDiversas[idx] = bet; else _allDiversas.unshift(bet);
    } else {
      _allDiversas.unshift(bet);
    }
    const msg = _editingDiversaId ? '✅ Aposta atualizada!' : '✅ Aposta adicionada!';
    fecharFormularioDv();
    renderDiversas();
    showToast(msg);
  } else {
    showToast('❌ Erro ao salvar aposta');
  }
}

// ── Delete ────────────────────────────────────────────────────────────────
async function excluirDiversa() {
  if (!_editingDiversaId) return;
  if (!confirm('Excluir esta aposta? Esta ação não pode ser desfeita.')) return;

  const res = await authFetch(`/api/bets-diversas/${_editingDiversaId}`, { method: 'DELETE' });
  if (res.ok || res.status === 204) {
    _allDiversas = _allDiversas.filter(b => b.bet_id !== _editingDiversaId);
    fecharFormularioDv();
    renderDiversas();
    showToast('🗑 Aposta excluída');
  } else {
    showToast('❌ Erro ao excluir aposta');
  }
}

// ── Print / CSV import ────────────────────────────────────────────────────
function abrirPrintModalDv() {
  const modal = document.getElementById('printModalOverlayDv');
  if (!modal) return;
  modal.style.display = 'flex';
  _printModalOpenDv = true;
  setTimeout(() => document.getElementById('pasteZoneDv')?.focus(), 60);
}

function fecharPrintModalDv() {
  const modal = document.getElementById('printModalOverlayDv');
  if (!modal) return;
  modal.style.display = 'none';
  _printModalOpenDv = false;
  const preview = document.getElementById('pastePreviewDv');
  if (preview) preview.style.display = 'none';
  const status = document.getElementById('printStatusDv');
  if (status) status.textContent = '';
}

async function importarPrintFileDv(file) {
  const status = document.getElementById('printStatusDv');
  const preview = document.getElementById('pastePreviewDv');
  const previewImg = document.getElementById('pastePreviewImgDv');
  if (preview && previewImg) {
    previewImg.src = URL.createObjectURL(file);
    preview.style.display = 'block';
  }
  if (status) status.textContent = 'Analisando com IA...';

  const form = new FormData();
  form.append('file', file);
  const res = await authFetch('/api/bets-diversas/import-screenshot', { method: 'POST', body: form });
  if (res.ok) {
    const data = await res.json();
    fecharPrintModalDv();
    showToast(`✅ ${data.importadas} apostas importadas, ${data.ignoradas} ignoradas`);
    await loadDiversas();
  } else {
    const err = await res.json().catch(() => ({}));
    if (status) status.textContent = '❌ ' + (err.detail || 'Erro ao importar print');
  }
}

function importarPrintFromInputDv(input) {
  const file = input.files[0];
  if (file) importarPrintFileDv(file);
  input.value = '';
}

async function importarCSVDv(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  showToast('⏳ Importando...');
  const res = await authFetch('/api/bets-diversas/import', { method: 'POST', body: form });
  if (res.ok) {
    const data = await res.json();
    showToast(`✅ ${data.importadas} apostas importadas, ${data.ignoradas} ignoradas`);
    await loadDiversas();
  } else {
    showToast('❌ Erro ao importar CSV');
  }
  input.value = '';
}
