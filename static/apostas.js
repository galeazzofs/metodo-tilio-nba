// apostas.js — Aba Minhas Apostas
// Depende de: auth.js (authFetch), showToast (index.html)

let _allBets = [];

async function loadApostas() {
  const container = document.getElementById('tab-apostas');
  container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--muted)">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    _allBets = await res.json();
    renderApostas();
  } catch (e) {
    container.innerHTML = `<div style="padding:40px;text-align:center;color:#f87171">${e.message}</div>`;
  }
}

function renderApostas() {
  const container = document.getElementById('tab-apostas');

  const q   = (document.getElementById('filtroTexto')?.value || '').toLowerCase();
  const res = document.getElementById('filtroResultado')?.value || 'todos';
  const de  = document.getElementById('filtroDe')?.value  || '';
  const ate = document.getElementById('filtroAte')?.value || '';

  let bets = [..._allBets].sort((a, b) => b.data.localeCompare(a.data));
  if (q)   bets = bets.filter(b => b.partida?.toLowerCase().includes(q) || b.descricao?.toLowerCase().includes(q));
  if (res !== 'todos') bets = bets.filter(b => b.resultado === res);
  if (de)  bets = bets.filter(b => b.data >= de);
  if (ate) bets = bets.filter(b => b.data <= ate);

  const BADGE = {
    ganhou:   '<span style="background:rgba(52,211,153,.15);color:#34d399;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700">🟢 Ganhou</span>',
    perdeu:   '<span style="background:rgba(248,113,113,.15);color:#f87171;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700">🔴 Perdeu</span>',
    pendente: '<span style="background:rgba(251,191,36,.15);color:#fbbf24;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700">🟡 Pendente</span>',
    void:     '<span style="background:rgba(255,255,255,.08);color:#94a3b8;padding:2px 10px;border-radius:99px;font-size:11px;font-weight:700">⚪ Void</span>',
  };

  const lpColor = v => v == null ? 'var(--muted)' : v >= 0 ? '#34d399' : '#f87171';
  const lpText  = v => v == null ? '—' : (v >= 0 ? '+' : '') + 'R$ ' + Math.abs(v).toFixed(2);

  const rows = bets.length === 0
    ? `<tr><td colspan="7" style="text-align:center;padding:48px;color:var(--muted)">Nenhuma aposta encontrada.</td></tr>`
    : bets.map(b => `
        <tr style="border-bottom:1px solid var(--border)">
          <td style="padding:14px 12px;color:var(--muted);font-size:13px;white-space:nowrap">${b.data}</td>
          <td style="padding:14px 12px;font-weight:600">${escH(b.partida)}</td>
          <td style="padding:14px 12px;color:var(--soft);font-size:13px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escH(b.descricao)}">${escH(b.descricao)}</td>
          <td style="padding:14px 12px;text-align:right">${b.odds?.toFixed(2) ?? '—'}</td>
          <td style="padding:14px 12px;text-align:right;white-space:nowrap">R$ ${b.stake?.toFixed(2) ?? '—'}</td>
          <td style="padding:14px 12px">${BADGE[b.resultado] ?? b.resultado}</td>
          <td style="padding:14px 12px;text-align:right;font-weight:700;color:${lpColor(b.lucro_prejuizo)};white-space:nowrap">${lpText(b.lucro_prejuizo)}</td>
        </tr>`).join('');

  const emptyState = _allBets.length === 0 ? `
    <div style="text-align:center;padding:72px 24px;color:var(--muted)">
      <div style="font-size:48px;margin-bottom:16px">🎰</div>
      <p style="font-size:15px">Nenhuma aposta registrada ainda.<br>Importe do bet365 ou adicione manualmente.</p>
    </div>` : '';

  const inputStyle = 'padding:10px 14px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;outline:none;';

  container.innerHTML = `
    <div style="max-width:1100px;margin:0 auto;padding:32px 24px">

      <!-- Toolbar -->
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;flex-wrap:wrap">
        <h2 style="font-size:20px;font-weight:800;flex:1;letter-spacing:-.5px">Minhas Apostas</h2>
        <button onclick="abrirFormulario()"
          style="padding:10px 22px;background:var(--orange);border:none;border-radius:99px;color:#fff;font-weight:700;font-size:13px;cursor:pointer;letter-spacing:.5px">
          + Adicionar
        </button>
        <label style="padding:10px 22px;background:var(--card);border:1px solid var(--border);border-radius:99px;color:var(--text);font-weight:700;font-size:13px;cursor:pointer;letter-spacing:.5px">
          ↑ Importar do bet365
          <input type="file" accept=".csv" style="display:none" onchange="importarCSV(this)" />
        </label>
      </div>

      <!-- Filtros -->
      <div style="display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap">
        <input id="filtroTexto" placeholder="Buscar partida ou descrição…" oninput="renderApostas()"
          style="flex:1;min-width:200px;${inputStyle}" />
        <select id="filtroResultado" onchange="renderApostas()" style="${inputStyle}">
          <option value="todos">Todos</option>
          <option value="ganhou">Ganhou</option>
          <option value="perdeu">Perdeu</option>
          <option value="pendente">Pendente</option>
          <option value="void">Void</option>
        </select>
        <input type="date" id="filtroDe"  onchange="renderApostas()" style="${inputStyle}" />
        <input type="date" id="filtroAte" onchange="renderApostas()" style="${inputStyle}" />
      </div>

      ${emptyState || `
      <!-- Tabela -->
      <div style="overflow-x:auto;border:1px solid var(--border);border-radius:16px;background:var(--card)">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="border-bottom:1px solid var(--border)">
              ${['Data','Partida','Descrição','Odds','Stake','Resultado','L/P'].map(h =>
                `<th style="padding:12px;text-align:${h==='Odds'||h==='Stake'||h==='L/P'?'right':'left'};font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);font-weight:700">${h}</th>`
              ).join('')}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`}

      <!-- Painel lateral de nova aposta -->
      <div id="formPanel" style="display:none;position:fixed;top:0;right:0;bottom:0;width:400px;max-width:100vw;
           background:var(--surface);border-left:1px solid var(--border);padding:32px 28px;overflow-y:auto;z-index:200;
           box-shadow:-20px 0 60px rgba(0,0,0,.4)">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:28px">
          <h3 style="font-size:18px;font-weight:800">Nova Aposta</h3>
          <button onclick="fecharFormulario()" style="background:none;border:none;color:var(--muted);font-size:20px;cursor:pointer">✕</button>
        </div>
        ${fField('Partida',    'formPartida',   'text',   'Lakers vs Celtics')}
        ${fField('Descrição',  'formDescricao', 'text',   'LeBron Mais de 25.5')}
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:11px;color:var(--muted);margin-bottom:6px;font-weight:700;text-transform:uppercase;letter-spacing:.5px">Tipo</label>
          <select id="formTipo" style="width:100%;padding:12px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px">
            <option>Vencedor</option><option>Handicap</option><option>Totais</option><option>Jogador</option><option>Outro</option>
          </select>
        </div>
        ${fField('Odds',       'formOdds',  'number', '1.85')}
        ${fField('Stake (R$)', 'formStake', 'number', '50')}
        ${fField('Data',       'formData',  'date',   '')}
        <div style="margin-bottom:24px">
          <label style="display:block;font-size:11px;color:var(--muted);margin-bottom:6px;font-weight:700;text-transform:uppercase;letter-spacing:.5px">Resultado</label>
          <select id="formResultado" style="width:100%;padding:12px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px">
            <option value="pendente">Pendente</option>
            <option value="ganhou">Ganhou</option>
            <option value="perdeu">Perdeu</option>
            <option value="void">Void</option>
          </select>
        </div>
        <div style="display:flex;gap:10px">
          <button onclick="salvarAposta()"
            style="flex:1;padding:14px;background:var(--orange);border:none;border-radius:99px;color:#fff;font-weight:700;font-size:14px;cursor:pointer">
            Salvar Aposta
          </button>
          <button onclick="fecharFormulario()"
            style="padding:14px 18px;background:var(--card);border:1px solid var(--border);border-radius:99px;color:var(--text);cursor:pointer;font-size:14px">
            Cancelar
          </button>
        </div>
      </div>
    </div>`;
}

function fField(label, id, type, placeholder) {
  const today = type === 'date' ? new Date().toISOString().slice(0,10) : '';
  const val   = type === 'date' ? `value="${today}"` : '';
  return `<div style="margin-bottom:16px">
    <label style="display:block;font-size:11px;color:var(--muted);margin-bottom:6px;font-weight:700;text-transform:uppercase;letter-spacing:.5px">${label}</label>
    <input type="${type}" id="${id}" placeholder="${placeholder}" ${val}
      style="width:100%;padding:12px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;outline:none" />
  </div>`;
}

function abrirFormulario() { document.getElementById('formPanel').style.display = 'block'; }
function fecharFormulario() { document.getElementById('formPanel').style.display = 'none'; }

async function salvarAposta() {
  const body = {
    partida:    document.getElementById('formPartida').value,
    descricao:  document.getElementById('formDescricao').value,
    tipo_aposta: document.getElementById('formTipo').value,
    odds:       parseFloat(document.getElementById('formOdds').value),
    stake:      parseFloat(document.getElementById('formStake').value),
    data:       document.getElementById('formData').value,
    resultado:  document.getElementById('formResultado').value,
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

function escH(str) {
  return String(str ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
