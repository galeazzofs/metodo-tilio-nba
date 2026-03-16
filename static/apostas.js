// apostas.js — Aba Minhas Apostas

let _allBets = [];

async function loadApostas() {
  const container = document.getElementById('tab-apostas');
  container.innerHTML = '<div style="padding:60px;text-align:center;color:var(--muted);font-family:var(--font-mono);font-size:12px;letter-spacing:0.08em">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    _allBets = await res.json();
    renderApostas();
  } catch (e) {
    container.innerHTML = `<div style="padding:60px;text-align:center;color:var(--red);font-family:var(--font-mono);font-size:12px">${e.message}</div>`;
  }
}

function renderApostas() {
  const container = document.getElementById('tab-apostas');

  const q   = (document.getElementById('filtroTexto')?.value   || '').toLowerCase();
  const res = (document.getElementById('filtroResultado')?.value || 'todos');
  const de  = document.getElementById('filtroDe')?.value  || '';
  const ate = document.getElementById('filtroAte')?.value || '';

  let bets = [..._allBets].sort((a, b) => b.data.localeCompare(a.data));
  if (q)   bets = bets.filter(b => b.partida?.toLowerCase().includes(q) || b.descricao?.toLowerCase().includes(q));
  if (res !== 'todos') bets = bets.filter(b => b.resultado === res);
  if (de)  bets = bets.filter(b => b.data >= de);
  if (ate) bets = bets.filter(b => b.data <= ate);

  const BADGE = {
    ganhou:   '<span class="b-badge b-win">Ganhou</span>',
    perdeu:   '<span class="b-badge b-loss">Perdeu</span>',
    pendente: '<span class="b-badge b-pend">Pendente</span>',
    void:     '<span class="b-badge b-void">Void</span>',
  };

  const pnlClass = v => v == null ? 't-pnl-zero' : v >= 0 ? 't-pnl-pos' : 't-pnl-neg';
  const pnlText  = v => v == null ? '—' : (v >= 0 ? '+' : '') + 'R$ ' + Math.abs(v).toFixed(2);

  const rows = bets.length === 0
    ? `<tr><td colspan="7" style="text-align:center;padding:52px;color:var(--muted);font-family:var(--font-mono);font-size:11px;letter-spacing:0.08em">Nenhuma aposta encontrada.</td></tr>`
    : bets.map(b => `
        <tr>
          <td class="t-date">${escH(b.data)}</td>
          <td style="font-weight:600;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escH(b.partida)}</td>
          <td style="color:var(--soft);font-size:13px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escH(b.descricao)}">${escH(b.descricao)}</td>
          <td class="t-num" style="text-align:right">${b.odds?.toFixed(2) ?? '—'}</td>
          <td class="t-num" style="text-align:right;white-space:nowrap">R$ ${b.stake?.toFixed(2) ?? '—'}</td>
          <td>${BADGE[b.resultado] ?? escH(b.resultado)}</td>
          <td class="${pnlClass(b.lucro_prejuizo)}" style="text-align:right;white-space:nowrap">${pnlText(b.lucro_prejuizo)}</td>
        </tr>`).join('');

  const emptyState = _allBets.length === 0 ? `
    <div style="text-align:center;padding:80px 24px">
      <div style="font-size:44px;margin-bottom:16px;opacity:0.4">◎</div>
      <p style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;line-height:1.8">NENHUMA APOSTA REGISTRADA<br>Importe ou adicione manualmente.</p>
    </div>` : '';

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
          <label class="btn-outline" style="cursor:pointer">
            ◈ Print IA
            <input type="file" accept="image/*" style="display:none" onchange="importarPrint(this)" />
          </label>
        </div>
      </div>

      <!-- Filters -->
      <div class="filters-row">
        <input class="f-input" style="flex:1;min-width:200px" id="filtroTexto" placeholder="Buscar partida ou descrição…" oninput="renderApostas()" />
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

      ${emptyState || `
      <!-- Table -->
      <div class="t-wrap">
        <table class="t-table">
          <thead>
            <tr>
              <th>Data</th>
              <th>Partida</th>
              <th>Descrição</th>
              <th class="r">Odds</th>
              <th class="r">Stake</th>
              <th>Resultado</th>
              <th class="r">L/P</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`}
    </div>

    <!-- Form panel overlay -->
    <div id="formOverlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:198;backdrop-filter:blur(4px)" onclick="fecharFormulario()"></div>

    <!-- Form panel -->
    <div id="formPanel" style="display:none;position:fixed;top:0;right:0;bottom:0;width:400px;max-width:100vw;
         background:var(--surface);border-left:1px solid var(--border);overflow-y:auto;z-index:199;
         display:none;flex-direction:column;box-shadow:-20px 0 60px rgba(0,0,0,0.45)">
      <div class="fp-hdr">
        <span class="fp-title">NOVA APOSTA</span>
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
        <select class="fp-input" id="formResultado">
          <option value="pendente">Pendente</option>
          <option value="ganhou">Ganhou</option>
          <option value="perdeu">Perdeu</option>
          <option value="void">Void</option>
        </select>
      </div>
      <div class="fp-footer">
        <button class="btn-outline" style="flex:1" onclick="fecharFormulario()">Cancelar</button>
        <button class="btn-primary" style="flex:2" onclick="salvarAposta()">Salvar Aposta</button>
      </div>
    </div>`;

  // Set today's date on data field
  const dataInput = document.getElementById('formData');
  if (dataInput && !dataInput.value) {
    dataInput.value = new Date().toISOString().slice(0, 10);
  }
}

function abrirFormulario() {
  const panel = document.getElementById('formPanel');
  const overlay = document.getElementById('formOverlay');
  if (panel)   { panel.style.display = 'flex'; }
  if (overlay) { overlay.style.display = 'block'; }
}

function fecharFormulario() {
  const panel = document.getElementById('formPanel');
  const overlay = document.getElementById('formOverlay');
  if (panel)   { panel.style.display = 'none'; }
  if (overlay) { overlay.style.display = 'none'; }
}

async function salvarAposta() {
  const body = {
    partida:     document.getElementById('formPartida').value,
    descricao:   document.getElementById('formDescricao').value,
    tipo_aposta: document.getElementById('formTipo').value,
    odds:        parseFloat(document.getElementById('formOdds').value),
    stake:       parseFloat(document.getElementById('formStake').value),
    data:        document.getElementById('formData').value,
    resultado:   document.getElementById('formResultado').value,
  };
  const res = await authFetch('/api/bets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.ok) {
    const bet = await res.json();
    _allBets.unshift(bet);
    fecharFormulario();
    renderApostas();
    showToast('✅ Aposta adicionada!');
  } else {
    showToast('❌ Erro ao salvar aposta');
  }
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

async function importarPrint(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  showToast('⏳ Analisando print com IA...');
  const res = await authFetch('/api/bets/import-screenshot', { method: 'POST', body: form });
  if (res.ok) {
    const data = await res.json();
    showToast(`✅ ${data.importadas} apostas importadas, ${data.ignoradas} ignoradas`);
    await loadApostas();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast('❌ Erro ao importar print: ' + (err.detail || res.status));
  }
  input.value = '';
}

function escH(str) {
  return String(str ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
