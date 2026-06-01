/* ── STATE ─────────────────────────────────────────────────── */
const S = {
  user: null,
  client: null,
  companies: [],
  pages: [],
  section: 'performance',
  plan: [],
  planId: null,
  planMeta: { mode: 'monthly', focus: '', title: '', month_label: '' },
  brandProfile: {},
  selected: new Set(),
  reviewIdx: 0,
  reviewPlatform: 'instagram',
  reviewCarouselIdx: 0,
  contentTab: 'plan',
  calendarDate: new Date(),
  campaigns: {
    adAccountId: '',
    adAccountName: '',
    period: 'last_7d',
    report: null,
  },
  aiUsage: { byPost: {}, byOperation: {}, summary: {} },
  aiModels: {},
  _instaRunDiagnostics: null,
  admin: { users: [], pages: [], adAccounts: [], companies: {}, editingEmail: '' },
};

const IMAGE_UI_DEFAULTS = {
  size: '1024x1024',
  quality: 'auto',
  background: 'auto',
  output_format: 'png',
  moderation: 'auto',
};

const IMAGE_SELECT_OPTIONS = {
  size: [
    ['1024x1024', '1024 x 1024'],
    ['1024x1536', '1024 x 1536'],
    ['1536x1024', '1536 x 1024'],
  ],
  quality_openai_gpt_image: [
    ['auto', 'Auto'],
    ['low', 'Low'],
    ['medium', 'Medium'],
    ['high', 'High'],
  ],
  quality_openai_dalle3: [
    ['standard', 'Standard'],
    ['hd', 'HD'],
  ],
  quality_default: [
    ['standard', 'Standard'],
  ],
  background: [
    ['auto', 'Auto'],
    ['opaque', 'Opaque'],
    ['transparent', 'Transparent'],
  ],
  output_format: [
    ['png', 'PNG'],
    ['jpeg', 'JPEG'],
    ['webp', 'WEBP'],
  ],
  moderation: [
    ['auto', 'Auto'],
    ['low', 'Low'],
  ],
};

/* ── API ───────────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const timeoutMs = opts._timeout || 20000;
  delete opts._timeout;
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, signal: ctrl.signal, ...opts });
    clearTimeout(tid);
    const raw = await r.text();
    if (!raw.trim()) {
      return { ok: r.ok, status: r.status, error: r.ok ? '' : `Resposta vazia (${r.status})` };
    }
    try {
      return JSON.parse(raw);
    } catch (e) {
      return {
        ok: false,
        status: r.status,
        error: `Resposta invalida do servidor: ${String(e)}`,
        detail: raw.slice(0, 400),
      };
    }
  } catch (e) {
    clearTimeout(tid);
    if (e.name === 'AbortError') return { ok: false, error: 'Tempo limite excedido. Tente novamente.' };
    return { ok: false, error: String(e) };
  }
}
function post(path, body) { return api(path, { method: 'POST', body: JSON.stringify(body) }); }
function safeInt(value, fallback) {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? n : fallback;
}

function ensureSelectOptions(selectId, options, selected = '') {
  const el = q(`#${selectId}`);
  if (!el) return;
  const current = selected || el.value || '';
  el.innerHTML = (options || []).map(([value, label]) => `<option value="${esc(value)}">${esc(label)}</option>`).join('');
  const values = (options || []).map(([value]) => value);
  el.value = values.includes(current) ? current : (values[0] || '');
}

function replaceInputWithSelect(id) {
  const input = q(`#${id}`);
  if (!input || input.tagName === 'SELECT') return input;
  const select = document.createElement('select');
  select.id = input.id;
  select.className = input.className.replace('form-input', 'form-select');
  select.style.cssText = input.style.cssText || '';
  for (const attr of input.getAttributeNames()) {
    if (['id', 'class', 'style', 'type', 'value'].includes(attr)) continue;
    select.setAttribute(attr, input.getAttribute(attr));
  }
  input.replaceWith(select);
  return select;
}

function ensureImageConfigSelects() {
  ['cfg-ai-image-size', 'cfg-ai-image-quality', 'cfg-ai-image-background', 'cfg-ai-image-output-format', 'cfg-ai-image-moderation']
    .forEach(replaceInputWithSelect);
  const modelEl = q('#cfg-ai-image-model');
  if (modelEl && !modelEl.dataset.imageUiBound) {
    modelEl.addEventListener('change', () => updateImageSettingsUI());
    modelEl.dataset.imageUiBound = '1';
  }
}

/* ── INIT ──────────────────────────────────────────────────── */
async function init() {
  const me = await api('/auth/me');
  if (!me.ok || !me.user) { showLogin(); return; }
  S.user = me.user;
  q('#nav-admin')?.classList.toggle('hidden', S.user?.role !== 'admin');
  hideLogin();
  await loadCompanies();
  const urlSec = _PATH_TO_SEC[window.location.pathname];
  const targetSec = urlSec || 'performance';
  history.replaceState({ section: targetSec }, '', _SEC_TO_PATH[targetSec] || '/');
  if (targetSec === 'admin' || targetSec === 'agents') {
    goto(targetSec);
    return;
  }
  if (urlSec && urlSec !== 'performance') {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    q(`#sec-${urlSec}`)?.classList.add('active');
    document.querySelectorAll('.sb-nav a').forEach(a => a.classList.toggle('active', a.dataset.sec === urlSec));
    S.section = urlSec;
  }
  const saved = localStorage.getItem('panel_client_id');
  if (saved) {
    const c = S.companies.find(x => x.id === saved);
    if (c) { setClient(c); return; }
  }
  loadCurrentSection();
  openClientModal();
}

async function loadCompanies() {
  const r = await api('/panel/companies');
  if (r.ok) S.companies = Object.values(r.companies || {});
  const pr = await api('/panel/pages');
  if (pr.ok) S.pages = pr.pages || [];
}

/* ── AUTH ──────────────────────────────────────────────────── */
async function doLogin() {
  const email = q('#login-email').value.trim();
  const pw = q('#login-pw').value;
  if (!email || !pw) { q('#login-err').textContent = 'Preencha email e senha.'; return; }
  const r = await post('/auth/login', { email, password: pw });
  if (r.ok) { hideLogin(); S.user = r.user || {}; q('#nav-admin')?.classList.toggle('hidden', S.user?.role !== 'admin'); await loadCompanies(); openClientModal(); }
  else q('#login-err').textContent = r.error === 'invalid_credentials' ? 'Email ou senha incorretos.' : 'Erro ao entrar.';
}
async function doLogout() {
  await api('/auth/logout', { method: 'POST' });
  localStorage.removeItem('panel_client_id');
  location.reload();
}
function showLogin() { q('#login-screen').style.display = 'flex'; q('#app').style.display = 'none'; }
function hideLogin() { q('#login-screen').style.display = 'none'; q('#app').style.display = 'flex'; }

/* ── CLIENT ────────────────────────────────────────────────── */
function openClientModal() {
  renderClientList('');
  q('#client-search').value = '';
  openModal('modal-client');
}
function filterClients(v) { renderClientList(v); }
function renderClientList(filter) {
  const list = q('#client-list');
  const items = S.companies.filter(c => !filter || c.name.toLowerCase().includes(filter.toLowerCase()));
  const createBtn = `<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">
    <button class="btn btn-outline btn-sm" style="width:100%" onclick="createNewClient()">+ Criar novo cliente</button>
  </div>`;
  if (!items.length) {
    const unconverted = !filter ? (S.pages || []).filter(p =>
      !S.companies.some(c => String(c.bindings?.meta?.page_id || c.id) === String(p.id))
    ) : [];
    let html = '';
    if (unconverted.length) {
      html += `<div style="font-size:12px;color:var(--text-muted);padding:10px 4px 6px">Páginas Meta conectadas — clique para criar o cliente:</div>`;
      html += unconverted.map(p => `
        <div class="client-option" onclick="createCompanyFromPageAndSelect('${esc(String(p.id || ''))}')">
          <div class="client-avatar">${(p.name || 'P')[0].toUpperCase()}</div>
          <div><div class="client-opt-name">${esc(p.name || 'Página')}</div>
          <div class="client-opt-sub">${p.instagram_business_account?.username ? '@' + esc(p.instagram_business_account.username) : String(p.id || '')}</div></div>
        </div>`).join('');
    }
    const canConnect = S.user?.meta_connection_enabled !== false;
    html += `<div class="empty-state" style="padding:20px 0 8px">
      <p>Nenhum cliente encontrado.</p>
      ${canConnect && !filter ? `<a href="/meta/connect/start" class="btn btn-primary btn-sm" style="margin-top:12px;display:inline-block">Conectar conta Meta</a>` : ''}
    </div>`;
    html += createBtn;
    list.innerHTML = html;
    return;
  }
  list.innerHTML = items.map(c => `
    <div class="client-option ${S.client?.id === c.id ? 'selected' : ''}" onclick="selectClient('${c.id}')">
      <div class="client-avatar">${c.name[0].toUpperCase()}</div>
      <div><div class="client-opt-name">${esc(c.name)}</div>
      <div class="client-opt-sub">${c.bindings?.meta?.instagram?.username ? '@' + c.bindings.meta.instagram.username : c.id}</div></div>
    </div>`).join('') + createBtn;
}
async function createNewClient() {
  const name = prompt('Nome do novo cliente:');
  if (!name || !name.trim()) return;
  const r = await post('/panel/companies/upsert', { name: name.trim() });
  if (!r.ok) { alert(r.error || 'Erro ao criar cliente.'); return; }
  await loadCompanies();
  const co = S.companies.find(c => c.name === name.trim() || c.id === r.company?.id);
  if (co) { setClient(co); closeModal('modal-client'); }
}
function selectClient(id) {
  const c = S.companies.find(x => x.id === id);
  if (!c) return;
  setClient(c);
  closeModal('modal-client');
}
function setClient(company) {
  const binding = company.bindings?.meta || {};
  const ig = binding.instagram || {};
  const page = S.pages.find(p => String(p.id) === String(binding.page_id || company.id));
  S.client = {
    id: company.id, name: company.name,
    page_id: binding.page_id || company.id,
    ig_user_id: ig.ig_user_id || page?.instagram_business_account?.id || '',
    ig_username: ig.username || page?.instagram_business_account?.username || '',
    access_token: page?.access_token || '',
    instagram_connected: Boolean(ig.ig_user_id || page?.instagram_business_account?.id || ''),
    facebook_connected: Boolean(binding.page_id || page?.id || ''),
    ad_account_id: binding.ad_account_id || '',
  };
  S.brandProfile = {};
  S.plan = [];
  S.planId = null;
  S.selected.clear();
  S_AGENTS.config = null;
  clearAgentsSection();
  localStorage.setItem('panel_client_id', company.id);
  updateSidebarClient();
  loadCurrentSection();
}
function updateSidebarClient() {
  const c = S.client;
  const el = q('#sb-client');
  if (!c) { el.classList.add('empty'); q('#sb-avatar').textContent = '?'; q('#sb-name').textContent = 'Selecionar cliente'; q('#sb-label').textContent = 'Nenhum selecionado'; return; }
  el.classList.remove('empty');
  q('#sb-avatar').textContent = c.name[0].toUpperCase();
  q('#sb-name').textContent = c.name;
  q('#sb-label').textContent = c.ig_username ? '@' + c.ig_username : c.page_id;
}

/* ── NAVIGATION ────────────────────────────────────────────── */
const _SEC_TO_PATH = { performance: '/', campaigns: '/campanhas', content: '/conteudo', analysis: '/analise', icp: '/icp', settings: '/configuracoes', admin: '/admin', agents: '/agentes' };
const _PATH_TO_SEC = Object.fromEntries(Object.entries(_SEC_TO_PATH).map(([k,v])=>[v,k]));
function goto(sec) {
  S.section = sec;
  const path = _SEC_TO_PATH[sec] || '/';
  if (window.location.pathname !== path) history.pushState({ section: sec }, '', path);
  document.querySelectorAll('.sb-nav a').forEach(a => a.classList.toggle('active', a.dataset.sec === sec));
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  q(`#sec-${sec}`)?.classList.add('active');
  loadCurrentSection();
}
window.addEventListener('popstate', e => {
  const sec = e.state?.section || _PATH_TO_SEC[window.location.pathname] || 'performance';
  S.section = sec;
  document.querySelectorAll('.sb-nav a').forEach(a => a.classList.toggle('active', a.dataset.sec === sec));
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  q(`#sec-${sec}`)?.classList.add('active');
  loadCurrentSection();
});
function loadCurrentSection() {
  if (S.section === 'admin') { loadAdminSection(); return; }
  if (S.section === 'agents') { loadAgentsSection(); return; }
  if (S.section === 'settings') { loadSettings(); return; }
  const noClient = q('#home-no-client');
  if (!S.client) {
    if (noClient) noClient.style.display = '';
    return;
  }
  if (noClient) noClient.style.display = 'none';
  ({ performance: loadPerformance, campaigns: loadCampaigns, content: loadContent, analysis: loadAnalysis, icp: loadICP })[S.section]?.();
}

/* ── HOME / PERFORMANCE ────────────────────────────────────── */
function renderHomeBrandBar() {
  const bp = S.brandProfile || {};
  const bar = q('#home-brand-bar');
  const ob = q('#home-onboarding');
  if (!bar) return;

  const hasName = !!bp.brand_name;
  const hasDesc = !!bp.description;
  const hasLogo = !!bp.logo_url;
  const hasIG   = !!S.client?.ig_username;

  if (hasName) {
    bar.style.display = '';
    bar.classList.remove('hidden');
    const nameEl = q('#home-brand-name');
    const tagEl  = q('#home-brand-tagline');
    const logoEl = q('#home-brand-logo');
    if (nameEl) nameEl.textContent = bp.brand_name;
    if (tagEl)  tagEl.textContent  = bp.tagline || bp.description?.slice(0, 80) || '';
    if (logoEl && bp.logo_url) { logoEl.src = bp.logo_url; logoEl.style.display = ''; }
  }

  if (ob) {
    const steps = [
      { done: hasName, label: 'Nome da marca preenchido' },
      { done: hasDesc, label: 'Descrição da marca' },
      { done: hasLogo, label: 'Logo cadastrada' },
      { done: hasIG,   label: 'Instagram vinculado' },
    ];
    const missing = steps.filter(s => !s.done);
    if (missing.length > 0) {
      ob.classList.remove('hidden');
      q('#home-onboarding-steps').innerHTML = steps.map(s =>
        `<div style="display:flex;align-items:center;gap:8px;font-size:13px">
          <span style="color:${s.done ? 'var(--success)' : 'var(--text-muted)'}">${s.done ? '✓' : '○'}</span>
          <span style="color:${s.done ? 'var(--text-2)' : 'var(--text)'};text-decoration:${s.done ? 'line-through' : 'none'}">${s.label}</span>
        </div>`
      ).join('');
    } else {
      ob.classList.add('hidden');
    }
  }
}

async function loadHomeCurrentPlan() {
  const el = q('#home-current-plan');
  if (!el) return;
  const r = await api(`/panel/content-plans?page_id=${S.client.page_id}&limit=1`);
  if (!r.ok || !r.plans?.length) {
    el.innerHTML = `<div class="empty-state" style="padding:12px"><p style="margin:0 0 10px;font-size:13px">Nenhum plano gerado.</p><button class="btn btn-primary btn-sm" onclick="goto('content')">Criar plano →</button></div>`;
    return;
  }
  const plan = r.plans[0];
  const posts = plan.posts || [];
  const done  = posts.filter(p => p.status === 'approved' || p.status === 'published').length;
  const pct   = posts.length ? Math.round(done / posts.length * 100) : 0;
  el.innerHTML = `
    <div style="font-size:13px;font-weight:600;margin-bottom:6px">${esc(plan.title || plan.month_label || 'Plano atual')}</div>
    <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px">${posts.length} posts · ${done} aprovados</div>
    <div style="height:4px;background:var(--surface-2);border-radius:99px;overflow:hidden;margin-bottom:12px">
      <div style="width:${pct}%;height:100%;background:var(--primary);border-radius:99px"></div>
    </div>
    <button class="btn btn-outline btn-sm" onclick="goto('content')">Ver plano →</button>`;
}

async function loadPerformance() {
  q('#perf-title').textContent = S.client.name;
  q('#perf-sub').textContent = 'Últimos 30 dias · ' + (S.client.ig_username ? '@' + S.client.ig_username : S.client.page_id);
  ['reach','eng','follow','posts'].forEach(k => { q(`#m-${k}`).textContent = '—'; q(`#m-${k}-d`).textContent = ''; });
  if (!S.brandProfile.brand_name) {
    const r = await api('/panel/brand-profiles');
    if (r.ok) S.brandProfile = (r.profiles||{})[S.client.page_id] || {};
  }
  renderHomeBrandBar();
  loadInsights(); loadIntegrations(); loadRecentPosts(); loadHomeCurrentPlan();
}
async function loadInsights() {
  const r = await api(`/panel/insights/overview?page_id=${S.client.page_id}`);
  if (!r.ok) return;
  const d = r.data || {};
  if (d.reach_total||d.page_reach) q('#m-reach').textContent = formatNum(d.reach_total||d.page_reach);
  if (d.engagement_rate) q('#m-eng').textContent = d.engagement_rate+'%';
  if (d.followers_count||d.instagram_followers) q('#m-follow').textContent = formatNum(d.followers_count||d.instagram_followers);
  const sp = await api(`/schedule/posts?page_id=${S.client.page_id}&status=published`);
  if (sp.ok) { const ago = Date.now()/1000-30*86400; q('#m-posts').textContent = (sp.posts||[]).filter(p=>(p.published_at||p.scheduled_at)>=ago).length; }
}
async function loadIntegrations() {
  const c = S.client;
  const items = [
    { icon: '📸', name: 'Instagram', connected: !!c.ig_user_id, sub: c.ig_username ? '@'+c.ig_username : 'Não vinculado' },
    { icon: '👤', name: 'Facebook', connected: !!c.page_id, sub: 'Página vinculada' },
    { icon: '💼', name: 'LinkedIn', connected: false, sub: 'Não conectado' },
    { icon: '✖', name: 'X (Twitter)', connected: false, sub: 'Não conectado' },
  ];
  q('#perf-integrations').innerHTML = `<div class="status-list">${items.map(it => `
    <div class="status-item">
      <div class="status-item-left"><span class="status-item-icon">${it.icon}</span>
        <div><div class="status-item-name">${it.name}</div><div style="font-size:12px;color:var(--text-muted)">${it.sub}</div></div>
      </div>
      ${it.connected ? '<span class="badge badge-green"><span class="dot dot-green"></span>Ativo</span>' : '<span class="badge badge-gray"><span class="dot dot-gray"></span>Inativo</span>'}
    </div>`).join('')}</div>`;
}
async function loadRecentPosts() {
  const r = await api(`/schedule/posts?page_id=${S.client.page_id}&status=published`);
  if (!r.ok||!r.posts?.length) {
    q('#perf-activity').innerHTML = '<div class="empty-state"><p>Nenhuma atividade.</p></div>';
    q('#perf-posts-list').innerHTML = '<div class="empty-state"><div class="empty-icon">◻</div><h3>Sem posts publicados</h3></div>';
    return;
  }
  const posts = r.posts.slice(0,5);
  q('#perf-activity').innerHTML = posts.slice(0,3).map(p=>`
    <div style="display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)">
      <span class="badge badge-green" style="flex-shrink:0">Publicado</span>
      <div style="min-width:0;flex:1"><div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(p.ig_username?'@'+p.ig_username:p.page_name)}</div>
      <div style="font-size:11px;color:var(--text-muted)">${fmtDate(p.published_at||p.scheduled_at)}</div></div>
    </div>`).join('');
  q('#perf-posts-list').innerHTML = `<div class="posts-list">${posts.map(p=>`
    <div class="post-row">
      ${p.image_url?`<img class="post-thumb" src="${p.image_url}" onerror="this.style.display='none'"/>`:'<div class="post-thumb"></div>'}
      <div class="post-info"><div class="post-name">${esc(p.page_name||'Post')}</div>
      <div class="post-meta">${fmtDate(p.published_at||p.scheduled_at)}</div>
      ${p.caption?`<div class="post-caption">${esc(p.caption.substring(0,120))}</div>`:''}</div>
      <span class="badge badge-green">Publicado</span>
    </div>`).join('')}</div>`;
}

/* ── CAMPAIGNS ─────────────────────────────────────────────── */
/* ── CAMPAIGNS ──────────────────────────────────────────────── */
const S_CHARTS = { spend: null, objective: null };

function switchCampaignTab(tab, el) {
  document.querySelectorAll('.campaigns-tab').forEach(t => t.style.display = 'none');
  const active = q(`#campaigns-tab-${tab}`);
  if (active) active.style.display = '';
  document.querySelectorAll('#sec-campaigns .tabs-row .tab-btn').forEach(b => b.classList.remove('active'));
  el?.classList.add('active');
  if (tab === 'drafts') loadCampaignDrafts();
  if (tab === 'history') loadCampaignHistory();
}

async function loadCampaigns() {
  const r = await api(`/panel/campaigns/context?page_id=${encodeURIComponent(S.client?.page_id || '')}`);
  const container = q('#campaigns-ad-accounts');
  if (!r.ok || !r.ad_accounts?.length) {
    container.innerHTML = '<a href="/meta/connect/start" style="color:var(--primary);font-size:13px">Conectar conta Meta →</a>';
    return;
  }
  const accounts = r.ad_accounts || [];
  const preferredId = r.preferred_ad_account_id || '';
  const boundId = r.bound_ad_account_id || '';
  container.innerHTML = accounts.map(a => {
    const active = S.campaigns.adAccountId === a.id;
    const isBound = a._bound === true;
    const suggested = !isBound && (a._suggested || preferredId === a.id);
    const hint = Array.isArray(a._match_reasons) && a._match_reasons.length ? ` title="${esc(a._match_reasons.join(' | '))}"` : '';
    const label = isBound ? ' · <strong>vinculada</strong>' : (suggested ? ' · sugerida' : '');
    return `<button class="btn btn-outline btn-sm ${active ? 'active' : ''}" onclick="loadAdCampaigns('${a.id}','${esc(a.name)}')"${hint}>${esc(a.name)}${label}</button>`;
  }).join('');
  if (q('#campaigns-period')) q('#campaigns-period').value = S.campaigns.period || 'last_7d';
  // Prioridade: conta vinculada > preferred > suggested > primeira
  const autoSelect = accounts.find(a => a._bound) || accounts.find(a => a.id === preferredId) || accounts.find(a => a._suggested) || accounts[0];
  if (!S.campaigns.adAccountId && autoSelect) {
    S.campaigns.adAccountId = autoSelect.id;
    S.campaigns.adAccountName = autoSelect.name || autoSelect.id;
  }
  if (S.campaigns.adAccountId) await loadAdCampaigns(S.campaigns.adAccountId, S.campaigns.adAccountName, true);
}
async function loadAdCampaigns(adAccountId, name, preserve = false) {
  S.campaigns.adAccountId = adAccountId;
  S.campaigns.adAccountName = name;
  await post('/panel/campaigns/context/save', {
    page_id: S.client?.page_id || '',
    preferred_ad_account_id: adAccountId,
  });
  S.campaigns.period = q('#campaigns-period')?.value || S.campaigns.period || 'last_7d';
  const acctEl = q('#campaigns-selected-account');
  if (acctEl) acctEl.textContent = `${name} · ${adAccountId}`;
  const analyzeBtn = q('#btn-campaigns-analyze');
  if (analyzeBtn) analyzeBtn.disabled = false;
  // Highlight selected account button
  document.querySelectorAll('#campaigns-ad-accounts .btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#campaigns-ad-accounts .btn').forEach(b => { if (b.textContent.trim() === name) b.classList.add('active'); });
  if (!preserve) {
    q('#campaigns-summary').innerHTML = '';
    q('#campaigns-ai-summary').innerHTML = '';
    q('#campaigns-intelligence').innerHTML = '';
  }
  const listEl = q('#campaigns-list');
  if (listEl) listEl.innerHTML = '<div class="loading-state"><div class="spinner"></div>Carregando...</div>';
  const r = await api(`/meta/ad-performance-tree?ad_account_id=${adAccountId}&date_preset=${encodeURIComponent(S.campaigns.period)}&limit=250`);
  if (!r.ok || !r.campaigns?.length) {
    if (listEl) listEl.innerHTML = `<div class="empty-state"><div class="empty-icon">◈</div><h3>Sem campanhas</h3><p>${esc(name)}</p></div>`;
    return;
  }
  S.campaigns.tree = r;
  renderCampaignDashboard(r);
}

function renderCampaignDashboard(treePayload) {
  const campaigns = treePayload.campaigns || [];
  const summary = treePayload.summary || {};
  // KPI cards
  const kpiRow = q('#campaigns-kpi-row');
  if (kpiRow) {
    const totalLeads = campaigns.reduce((s, n) => s + Number((n.metrics || {}).leads || 0), 0);
    const totalClicks = campaigns.reduce((s, n) => s + Number((n.metrics || {}).clicks || 0), 0);
    const avgCTR = campaigns.length ? (campaigns.reduce((s, n) => s + Number((n.metrics || {}).ctr || 0), 0) / campaigns.length) : 0;
    const avgCPC = campaigns.length ? (campaigns.reduce((s, n) => s + Number((n.metrics || {}).cpc || 0), 0) / campaigns.filter(n => Number((n.metrics || {}).cpc || 0) > 0).length || 1) : 0;
    const totalImpr = campaigns.reduce((s, n) => s + Number((n.metrics || {}).impressions || 0), 0);
    const active = campaigns.filter(n => ((n.campaign?.effective_status || n.campaign?.status) === 'ACTIVE')).length;
    kpiRow.innerHTML = [
      { label: 'Investimento', value: `R$ ${Number(summary.spend || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}`, icon: '💰' },
      { label: 'Cliques', value: formatNum(totalClicks), icon: '👆' },
      { label: 'CTR médio', value: `${avgCTR.toFixed(2)}%`, icon: '📊' },
      { label: 'CPC médio', value: `R$ ${avgCPC.toFixed(2)}`, icon: '💸' },
      { label: 'Impressões', value: formatNum(totalImpr), icon: '👁' },
      { label: 'Ativas', value: `${active} / ${campaigns.length}`, icon: '✅' },
    ].map(k => `
      <div class="card" style="padding:14px;text-align:center">
        <div style="font-size:22px;margin-bottom:4px">${k.icon}</div>
        <div style="font-size:18px;font-weight:700;color:var(--text)">${k.value}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${k.label}</div>
      </div>`).join('');
  }
  // Charts
  renderCampaignCharts(campaigns);
  // Tree
  const c = q('#campaigns-list');
  if (c) c.innerHTML = `<div style="display:flex;flex-direction:column;gap:12px">${campaigns.map(n => campaignTreeHTML(n)).join('')}</div>`;
}

function renderCampaignCharts(campaigns) {
  if (!campaigns.length || typeof Chart === 'undefined') return;
  const chartsRow = q('#campaigns-charts-row');
  if (chartsRow) chartsRow.style.display = 'grid';
  // Spend bar chart — top 8 campaigns
  const top = [...campaigns].sort((a, b) => Number((b.metrics||{}).spend||0) - Number((a.metrics||{}).spend||0)).slice(0, 8);
  const spendCtx = q('#chart-spend');
  if (spendCtx) {
    if (S_CHARTS.spend) S_CHARTS.spend.destroy();
    S_CHARTS.spend = new Chart(spendCtx, {
      type: 'bar',
      data: {
        labels: top.map(n => (n.campaign?.name || 'Campanha').substring(0, 22)),
        datasets: [
          { label: 'Investimento (R$)', data: top.map(n => Number((n.metrics||{}).spend||0)), backgroundColor: '#6366f1cc', borderRadius: 6 },
          { label: 'Cliques', data: top.map(n => Number((n.metrics||{}).clicks||0)), backgroundColor: '#22d3ee88', borderRadius: 6, yAxisID: 'y2' },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { font: { size: 11 } } } },
        scales: {
          x: { ticks: { font: { size: 10 } } },
          y: { ticks: { font: { size: 10 } } },
          y2: { position: 'right', grid: { drawOnChartArea: false }, ticks: { font: { size: 10 } } },
        },
      },
    });
    spendCtx.parentElement.style.height = '220px';
  }
  // Objective donut
  const objMap = {};
  campaigns.forEach(n => {
    const obj = n.campaign?.objective || 'Outro';
    objMap[obj] = (objMap[obj] || 0) + Number((n.metrics||{}).spend||0);
  });
  const objCtx = q('#chart-objective');
  if (objCtx && Object.keys(objMap).length) {
    if (S_CHARTS.objective) S_CHARTS.objective.destroy();
    const colors = ['#6366f1','#22d3ee','#f59e0b','#10b981','#f43f5e','#8b5cf6'];
    S_CHARTS.objective = new Chart(objCtx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(objMap),
        datasets: [{ data: Object.values(objMap), backgroundColor: colors, borderWidth: 2 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 10 } } },
      },
    });
    objCtx.parentElement.style.height = '220px';
  }
}

function renderCampaignTree(treePayload) {
  // Legacy compatibility
  renderCampaignDashboard(treePayload);
}

function campaignTreeHTML(node) {
  const campaign = node.campaign || {};
  const metrics = node.metrics || {};
  const adsets = node.adsets || [];
  return `<div class="card" style="background:var(--surface-2)">
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
      <div>
        <div style="font-size:15px;font-weight:700">${esc(campaign.name || 'Campanha')}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:4px">${esc(campaign.objective || '')} · CTR ${Number(metrics.ctr || 0).toFixed(2)}% · CPC R$ ${Number(metrics.cpc || 0).toFixed(2)} · Spend R$ ${Number(metrics.spend || 0).toFixed(2)}</div>
      </div>
      <span class="badge ${(campaign.effective_status||campaign.status)==='ACTIVE'?'badge-green':(campaign.effective_status||campaign.status)==='PAUSED'?'badge-yellow':'badge-gray'}">${esc(campaign.effective_status || campaign.status || '')}</span>
    </div>
    ${adsets.length ? `<div style="display:flex;flex-direction:column;gap:10px;margin-top:14px">${adsets.map(adsetNode => adsetTreeHTML(adsetNode)).join('')}</div>` : '<div style="font-size:12px;color:var(--text-muted);margin-top:12px">Sem conjuntos carregados.</div>'}
  </div>`;
}

function adsetTreeHTML(node) {
  const adset = node.adset || {};
  const metrics = node.metrics || {};
  const ads = node.ads || [];
  return `<div style="padding:12px;border:1px solid var(--border);border-radius:14px;background:var(--bg)">
    <div style="font-size:13px;font-weight:700">${esc(adset.name || 'Conjunto')}</div>
    <div style="font-size:12px;color:var(--text-muted);margin-top:4px">CTR ${Number(metrics.ctr || 0).toFixed(2)}% · CPC R$ ${Number(metrics.cpc || 0).toFixed(2)} · Spend R$ ${Number(metrics.spend || 0).toFixed(2)} · Impressões ${formatNum(metrics.impressions || 0)}</div>
    ${ads.length ? `<div style="display:flex;flex-direction:column;gap:8px;margin-top:10px">${ads.map(adNode => adTreeHTML(adNode)).join('')}</div>` : '<div style="font-size:12px;color:var(--text-muted);margin-top:8px">Sem anúncios neste conjunto.</div>'}
  </div>`;
}

function adTreeHTML(node) {
  const ad = node.ad || {};
  const metrics = node.metrics || {};
  return `<div style="padding:10px;border:1px dashed var(--border);border-radius:12px;background:var(--surface-2)">
    <div style="font-size:12px;font-weight:700">${esc(ad.name || 'Anúncio')}</div>
    <div style="font-size:11px;color:var(--text-muted);margin-top:4px">Cliques ${formatNum(metrics.clicks || 0)} · CTR ${Number(metrics.ctr || 0).toFixed(2)}% · CPC R$ ${Number(metrics.cpc || 0).toFixed(2)} · CPM R$ ${Number(metrics.cpm || 0).toFixed(2)} · Spend R$ ${Number(metrics.spend || 0).toFixed(2)}</div>
  </div>`;
}

async function refreshCampaignTree() {
  if (!S.campaigns.adAccountId) return;
  await loadAdCampaigns(S.campaigns.adAccountId, S.campaigns.adAccountName, true);
}

async function analyzeTrafficAgent() {
  if (!S.campaigns.adAccountId) return;
  const period = q('#campaigns-period')?.value || S.campaigns.period || 'last_7d';
  const intEl = q('#campaigns-intelligence');
  const sumEl = q('#campaigns-ai-summary');
  if (intEl) intEl.innerHTML = '<div class="loading-state"><div class="spinner"></div>Analisando com IA...</div>';
  const r = await api(`/panel/ads/report?ad_account_id=${S.campaigns.adAccountId}&date_preset=${encodeURIComponent(period)}`);
  if (!r.ok) {
    if (intEl) intEl.innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao analisar.');
    return;
  }
  S.campaigns.report = r.report || null;
  renderTrafficIntelligence(r.report || {});
  // AI summary as formatted cards, not a text wall
  const summary = r.report_summary || {};
  const aiText = r.ai_summary || '';
  const bullets = aiText.split('\n').filter(l => l.trim());
  if (sumEl) sumEl.innerHTML = `
    <div class="card mt-16">
      <div class="card-title mb-12">Análise do Gestor IA · ${summary.active_campaigns || 0} ativas · ${summary.paused_campaigns || 0} pausadas</div>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${bullets.map(b => `<div style="font-size:13px;line-height:1.5;padding:6px 10px;border-left:3px solid var(--primary,#6366f1);background:var(--surface-alt,#f7f7f8);border-radius:0 6px 6px 0">${esc(b.replace(/^[-•*]\s*/,''))}</div>`).join('')}
      </div>
    </div>`;
  // Switch to intelligence tab
  const tabBtn = document.querySelector('#sec-campaigns .tabs-row .tab-btn:nth-child(2)');
  switchCampaignTab('intelligence', tabBtn);
  await loadCampaignHistory();
  showCampaignAlert('success', 'Análise atualizada.');
}

function renderTrafficIntelligence(report) {
  const el = q('#campaigns-intelligence');
  if (!el || !report) return;
  const campaigns = Array.isArray(report.campaigns) ? report.campaigns.slice() : [];
  const adsets = Array.isArray(report.adsets) ? report.adsets.slice() : [];
  const ads = Array.isArray(report.ads) ? report.ads.slice() : [];
  const bySpend = [...campaigns].sort((a, b) => Number((b.performance || {}).spend || 0) - Number((a.performance || {}).spend || 0));
  const byCTR = [...campaigns].sort((a, b) => Number((b.performance || {}).ctr || 0) - Number((a.performance || {}).ctr || 0));
  const byCPC = [...campaigns].sort((a, b) => Number((a.performance || {}).cpc || 999999) - Number((b.performance || {}).cpc || 999999));
  const bestCampaign = byCTR[0] || bySpend[0] || null;
  const worstCampaign = [...campaigns].sort((a, b) => Number((a.performance || {}).ctr || 0) - Number((b.performance || {}).ctr || 0))[0] || null;
  const bestAdset = [...adsets].sort((a, b) => Number((b.performance || {}).clicks || 0) - Number((a.performance || {}).clicks || 0))[0] || null;
  const bestAd = [...ads].sort((a, b) => Number((b.performance || {}).clicks || 0) - Number((a.performance || {}).clicks || 0))[0] || null;
  const bestAudience = extractAudienceSummary(bestAdset?.targeting || {});
  const bestCreative = bestAd ? `${bestAd.name || 'Anúncio'}${bestAd.creative?.name ? ` · ${bestAd.creative.name}` : ''}` : '';
  el.innerHTML = `
    <div class="grid2 gap-16">
      <div class="card" style="background:var(--surface-2)">
        <div class="card-title">Melhor campanha</div>
        ${bestCampaign ? `<div style="font-size:14px;font-weight:700">${esc(bestCampaign.name || '')}</div><div style="font-size:12px;color:var(--text-muted);margin-top:6px">CTR ${Number((bestCampaign.performance || {}).ctr || 0).toFixed(2)}% · CPC R$ ${Number((bestCampaign.performance || {}).cpc || 0).toFixed(2)} · Spend R$ ${Number((bestCampaign.performance || {}).spend || 0).toFixed(2)}</div>` : '<div style="font-size:12px;color:var(--text-muted)">Sem dados suficientes.</div>'}
      </div>
      <div class="card" style="background:var(--surface-2)">
        <div class="card-title">Pior campanha</div>
        ${worstCampaign ? `<div style="font-size:14px;font-weight:700">${esc(worstCampaign.name || '')}</div><div style="font-size:12px;color:var(--text-muted);margin-top:6px">CTR ${Number((worstCampaign.performance || {}).ctr || 0).toFixed(2)}% · CPC R$ ${Number((worstCampaign.performance || {}).cpc || 0).toFixed(2)} · Spend R$ ${Number((worstCampaign.performance || {}).spend || 0).toFixed(2)}</div>` : '<div style="font-size:12px;color:var(--text-muted)">Sem dados suficientes.</div>'}
      </div>
      <div class="card" style="background:var(--surface-2)">
        <div class="card-title">Público que mais clicou</div>
        ${bestAdset ? `<div style="font-size:14px;font-weight:700">${esc(bestAdset.name || '')}</div><div style="font-size:12px;color:var(--text-muted);margin-top:6px">${esc(bestAudience || 'Sem targeting estruturado disponível')} · ${formatNum((bestAdset.performance || {}).clicks || 0)} cliques</div>` : '<div style="font-size:12px;color:var(--text-muted)">Sem dados suficientes.</div>'}
      </div>
      <div class="card" style="background:var(--surface-2)">
        <div class="card-title">Criativo com mais cliques</div>
        ${bestAd ? `<div style="font-size:14px;font-weight:700">${esc(bestCreative)}</div><div style="font-size:12px;color:var(--text-muted);margin-top:6px">${formatNum((bestAd.performance || {}).clicks || 0)} cliques · CTR ${Number((bestAd.performance || {}).ctr || 0).toFixed(2)}%</div>` : '<div style="font-size:12px;color:var(--text-muted)">Sem dados suficientes.</div>'}
      </div>
    </div>`;
}

function extractAudienceSummary(targeting = {}) {
  if (!targeting || typeof targeting !== 'object') return '';
  const parts = [];
  if (targeting.age_min || targeting.age_max) parts.push(`${targeting.age_min || '?'}-${targeting.age_max || '?'} anos`);
  if (Array.isArray(targeting.genders) && targeting.genders.length) {
    parts.push(targeting.genders.includes(2) ? 'feminino' : targeting.genders.includes(1) ? 'masculino' : 'todos');
  }
  const locations = targeting.geo_locations?.cities || targeting.geo_locations?.regions || targeting.geo_locations?.countries || [];
  if (Array.isArray(locations) && locations.length) {
    const loc = locations[0];
    parts.push(loc.name || loc.key || String(loc));
  }
  const interests = targeting.flexible_spec?.flatMap(x => x.interests || []) || targeting.interests || [];
  if (Array.isArray(interests) && interests.length) parts.push(interests.slice(0, 3).map(i => i.name || i.id || String(i)).join(', '));
  return parts.filter(Boolean).join(' · ');
}

async function loadCampaignHistory() {
  if (!S.campaigns.adAccountId) return;
  const r = await api(`/panel/ads-report-history?ad_account_id=${encodeURIComponent(S.campaigns.adAccountId)}`);
  const el = q('#campaigns-history');
  if (!el) return;
  if (!r.ok || !Array.isArray(r.reports) || !r.reports.length) {
    el.innerHTML = '';
    return;
  }
  el.innerHTML = `<div class="card" style="margin-top:12px;background:var(--surface-2)">
    <div class="card-title">Histórico salvo de análises</div>
    <div style="display:flex;flex-direction:column;gap:10px">${r.reports.slice().reverse().slice(0, 6).map(item => `
      <div style="padding:10px;border:1px solid var(--border);border-radius:12px;background:var(--bg)">
        <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap">
          <div style="font-size:12px;color:var(--text-muted)">${fmtDate(item.ts)} · ${esc(item.date_preset || '')}</div>
          <div style="font-size:12px;color:var(--text-muted)">Spend R$ ${Number((item.totals || {}).spend || 0).toFixed(2)} · CTR ${Number((item.totals || {}).ctr || 0).toFixed(2)}%</div>
        </div>
        <div style="white-space:pre-wrap;font-size:12px;line-height:1.55;margin-top:8px">${esc(item.ai_summary || '')}</div>
      </div>`).join('')}</div>
  </div>`;
}

function openCampaignCreateModal() {
  if (!S.campaigns.adAccountId) { showCampaignAlert('error', 'Selecione uma conta de anúncios primeiro.'); return; }
  q('#campaign-create-alert').innerHTML = '';
  q('#campaign-create-account').textContent = `${S.campaigns.adAccountName} · ${S.campaigns.adAccountId}`;
  q('#campaign-create-name').value = '';
  q('#campaign-create-adset-name').value = 'Público principal';
  q('#campaign-create-daily-budget').value = '3000';
  q('#campaign-create-objective').value = 'OUTCOME_LEADS';
  const bestAdset = (S.campaigns.report?.adsets || []).slice().sort((a, b) => Number((b.performance || {}).clicks || 0) - Number((a.performance || {}).clicks || 0))[0];
  const targeting = bestAdset?.targeting || {};
  q('#campaign-create-age-min').value = targeting.age_min || 25;
  q('#campaign-create-age-max').value = targeting.age_max || 45;
  q('#campaign-create-gender').value = Array.isArray(targeting.genders) && targeting.genders[0] === 2 ? 'female' : Array.isArray(targeting.genders) && targeting.genders[0] === 1 ? 'male' : '';
  q('#campaign-create-location').value = targeting.geo_locations?.cities?.[0]?.name || targeting.geo_locations?.regions?.[0]?.name || '';
  const interests = targeting.flexible_spec?.flatMap(x => x.interests || []) || targeting.interests || [];
  q('#campaign-create-interests').value = Array.isArray(interests) ? interests.slice(0, 5).map(i => i.name || '').filter(Boolean).join(', ') : '';
  q('#campaign-create-suggestion').textContent = bestAdset ? `Base sugerida a partir do conjunto com mais cliques: ${bestAdset.name || ''}. Público: ${extractAudienceSummary(targeting) || 'sem targeting estruturado.'}` : 'Sem histórico suficiente para sugerir público automaticamente.';
  openModal('modal-campaign-create');
}

async function createTrafficCampaign() {
  if (!S.campaigns.adAccountId) return;
  setBtnLoading('#btn-campaign-create-confirm', true, 'Criando...');
  const interestNames = q('#campaign-create-interests').value.split(',').map(s => s.trim()).filter(Boolean);
  const r = await post('/meta/ad-drafts/create-campaign', {
    ad_account_id: S.campaigns.adAccountId,
    campaign_name: q('#campaign-create-name').value.trim(),
    adset_name: q('#campaign-create-adset-name').value.trim(),
    daily_budget: q('#campaign-create-daily-budget').value.trim(),
    objective: q('#campaign-create-objective').value,
    page_id: S.client?.page_id || '',
    instagram_actor_id: S.client?.ig_user_id || '',
    targeting: {
      age_min: parseInt(q('#campaign-create-age-min').value || '25', 10),
      age_max: parseInt(q('#campaign-create-age-max').value || '45', 10),
      ...(q('#campaign-create-gender').value === 'female' ? { genders: [2] } : {}),
      ...(q('#campaign-create-gender').value === 'male' ? { genders: [1] } : {}),
      ...(q('#campaign-create-location').value.trim() ? { geo_locations: { cities: [{ name: q('#campaign-create-location').value.trim() }] } } : {}),
      ...(interestNames.length ? { flexible_spec: [{ interests: interestNames.map(name => ({ name })) }] } : {}),
    },
  });
  setBtnLoading('#btn-campaign-create-confirm', false, 'Criar campanha');
  if (!r.ok) {
    q('#campaign-create-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao criar campanha.');
    return;
  }
  closeModal('modal-campaign-create');
  showCampaignAlert('success', `Campanha criada: ${r.campaign?.name || 'nova campanha'}`);
  await refreshCampaignTree();
}

function showCampaignAlert(type, msg) {
  const el = q('#campaigns-alert');
  if (!el) return;
  el.innerHTML = mkAlert(type, msg);
  setTimeout(() => { if (q('#campaigns-alert')) q('#campaigns-alert').innerHTML = ''; }, 5000);
}

/* ── CAMPAIGN DRAFTS ────────────────────────────────────────── */
async function loadCampaignDrafts() {
  if (!S.campaigns.adAccountId) { q('#campaigns-drafts-list').innerHTML = '<div class="muted">Selecione uma conta de anúncios primeiro.</div>'; return; }
  const r = await api(`/meta/ad-performance-tree?ad_account_id=${S.campaigns.adAccountId}&date_preset=last_30d&limit=100`);
  const el = q('#campaigns-drafts-list');
  if (!el) return;
  if (!r.ok) { el.innerHTML = mkAlert('error', r.error || 'Erro'); return; }
  const drafts = (r.campaigns || []).filter(n => {
    const st = ((n.campaign?.effective_status || n.campaign?.status) || '').toUpperCase();
    return st === 'PAUSED' || st === 'DRAFT';
  });
  if (!drafts.length) { el.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div><h3>Nenhum rascunho</h3><p>Crie uma campanha com o Gestor IA para ver aqui.</p></div>'; return; }
  el.innerHTML = `<div style="display:flex;flex-direction:column;gap:12px">${drafts.map(n => {
    const c = n.campaign || {};
    const m = n.metrics || {};
    const st = (c.effective_status || c.status || '').toUpperCase();
    return `<div class="card" style="background:var(--surface-2)">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
        <div>
          <div style="font-weight:700;font-size:14px">${esc(c.name || 'Campanha')}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:4px">${esc(c.objective || '')} · Spend R$ ${Number(m.spend||0).toFixed(2)}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <span class="badge badge-yellow">${st}</span>
          <button class="btn btn-primary btn-sm" onclick="activateCampaignDraft('${c.id}')">▶ Ativar</button>
        </div>
      </div>
    </div>`;
  }).join('')}`;
}

async function activateCampaignDraft(campaignId) {
  if (!confirm('Ativar esta campanha?')) return;
  const r = await post('/meta/ad-drafts/activate', { campaign_id: campaignId });
  if (r.ok) { showCampaignAlert('success', 'Campanha ativada!'); loadCampaignDrafts(); }
  else showCampaignAlert('error', r.detail || r.error || 'Erro ao ativar.');
}

/* ── TRAFFIC WIZARD ─────────────────────────────────────────── */
const TW = { interests: [], forms: [], links: [], pixels: [], selectedInterests: new Set(), selectedLocations: new Set(), suggestion: {} };

function setTWStep(active) {
  [['#tw-pill-1', 1], ['#tw-pill-2', 2], ['#tw-pill-3', 3], ['#tw-pill-4', 4]].forEach(([sel, idx]) => {
    const el = q(sel);
    if (!el) return;
    el.className = `badge ${idx <= active ? 'badge-blue' : 'badge-gray'}`;
  });
}

function twGoPane(name) {
  ['structure', 'destination', 'review'].forEach((pane) => {
    const el = q(`#tw-pane-${pane}`);
    if (el) el.style.display = pane === name ? '' : 'none';
  });
  setTWStep(name === 'structure' ? 2 : name === 'destination' ? 3 : 4);
}

function twObjectiveMeta(objective) {
  const map = {
    OUTCOME_LEADS: { destination: 'form', optimization_goal: 'LEAD_GENERATION', billing_event: 'IMPRESSIONS', cta: 'SIGN_UP' },
    OUTCOME_TRAFFIC: { destination: 'url', optimization_goal: 'LINK_CLICKS', billing_event: 'IMPRESSIONS', cta: 'LEARN_MORE' },
    OUTCOME_SALES: { destination: 'pixel', optimization_goal: 'OFFSITE_CONVERSIONS', billing_event: 'IMPRESSIONS', cta: 'SHOP_NOW' },
    OUTCOME_ENGAGEMENT: { destination: 'url', optimization_goal: 'POST_ENGAGEMENT', billing_event: 'IMPRESSIONS', cta: 'LEARN_MORE' },
  };
  return map[objective] || map.OUTCOME_LEADS;
}

function syncTWDestinationUI(forceType = '') {
  const objective = q('#tw-camp-objective')?.value || q('#tw-objective')?.value || 'OUTCOME_LEADS';
  const meta = twObjectiveMeta(objective);
  let selected = forceType || document.querySelector('[name="tw-dest-type"]:checked')?.value || meta.destination;
  if (objective === 'OUTCOME_LEADS' && selected === 'pixel') selected = 'form';
  if (objective === 'OUTCOME_SALES' && selected === 'form') selected = 'pixel';
  const radio = q(`#tw-dest-${selected}-radio`);
  if (radio) radio.checked = true;
  if (q('#tw-dest-url-wrap')) q('#tw-dest-url-wrap').style.display = selected === 'url' ? '' : 'none';
  if (q('#tw-dest-form-wrap')) q('#tw-dest-form-wrap').style.display = selected === 'form' ? '' : 'none';
  if (q('#tw-dest-pixel-wrap')) q('#tw-dest-pixel-wrap').style.display = selected === 'pixel' ? '' : 'none';
}

function openTrafficWizard() {
  if (!S.campaigns.adAccountId) { showCampaignAlert('error', 'Selecione uma conta de anúncios primeiro.'); return; }
  q('#tw-step-1').style.display = '';
  q('#tw-step-2').style.display = 'none';
  q('#tw-step-3').style.display = 'none';
  q('#tw-alert').innerHTML = '';
  // Pre-fill product from brand profile
  const bp = S.brandProfile || {};
  const defaultProduct = bp.key_products || bp.best_offer || bp.description?.substring(0, 120) || '';
  q('#tw-product').value = defaultProduct;
  q('#tw-objective').value = 'OUTCOME_LEADS';
  q('#tw-budget').value = '50';
  if (q('#tw-context-summary')) q('#tw-context-summary').innerHTML = `<strong>Página:</strong> ${esc(S.client?.name || '—')}<br/><strong>Conta sugerida:</strong> ${esc(S.campaigns.adAccountName || S.campaigns.adAccountId || '—')}`;
  TW.selectedInterests = new Set();
  TW.selectedLocations = new Set();
  TW.forms = [];
  TW.links = [];
  TW.pixels = [];
  TW.suggestion = {};
  setTWStep(1);
  syncTWDestinationUI();
  openModal('modal-traffic-wizard');
}

function twBack() {
  q('#tw-step-3').style.display = 'none';
  q('#tw-step-1').style.display = '';
  setTWStep(1);
}

async function runTrafficWizard() {
  const product = (q('#tw-product')?.value || '').trim();
  if (!product) { q('#tw-alert').innerHTML = mkAlert('error', 'Descreva o produto ou serviço.'); return; }
  q('#tw-step-1').style.display = 'none';
  q('#tw-step-2').style.display = '';
  const msgs = [
    'Analisando campanhas e públicos da conta...',
    'Buscando localizações e interesses já usados...',
    'Buscando sugestões de interesse no Meta...',
    'Lendo links, formulários e criativos...',
    'Gerando recomendação com IA...',
  ];
  let mi = 0;
  const ticker = setInterval(() => { const el = q('#tw-loading-msg'); if (el && mi < msgs.length-1) el.textContent = msgs[++mi]; }, 3000);
  const r = await post('/panel/campaigns/wizard/analyze', {
    ad_account_id: S.campaigns.adAccountId,
    page_id: S.client?.page_id || '',
    product,
    objective: q('#tw-objective').value,
    budget: q('#tw-budget').value,
  });
  clearInterval(ticker);
  if (!r.ok) {
    q('#tw-step-2').style.display = 'none';
    q('#tw-step-1').style.display = '';
    q('#tw-alert').innerHTML = mkAlert('error', r.error || 'Erro ao analisar.');
    return;
  }

  TW.interests = r.interests || [];
  TW.forms = r.forms || [];
  TW.links = r.links || [];
  TW.pixels = r.pixels || [];
  TW.locations = r.historical_locations || [];
  TW.selectedInterests = new Set();
  TW.selectedLocations = new Set();

  const sug = r.suggestion || {};
  TW.suggestion = sug;
  const bestAge = r.best_age || {};

  // Pre-select AI-suggested interests (match by name)
  const sugNames = new Set((sug.interests_selected || []).map(s => s.toLowerCase()));
  TW.interests.forEach(i => {
    if (sugNames.has((i.name || '').toLowerCase())) TW.selectedInterests.add(i.id + ':' + i.name);
  });

  // Fill campaign fields
  if (q('#tw-camp-name')) q('#tw-camp-name').value = sug.campaign_name || product.substring(0, 50);
  if (q('#tw-camp-objective')) q('#tw-camp-objective').value = q('#tw-objective').value;
  if (q('#tw-camp-budget')) q('#tw-camp-budget').value = sug.budget_daily || Math.round(Number(q('#tw-budget').value) || 50);
  if (q('#tw-age-min')) q('#tw-age-min').value = sug.age_min || bestAge.age_min || 25;
  if (q('#tw-age-max')) q('#tw-age-max').value = sug.age_max || bestAge.age_max || 55;
  if (q('#tw-headline')) q('#tw-headline').value = sug.headline || '';
  if (q('#tw-primary-text')) q('#tw-primary-text').value = sug.primary_text || '';
  const whyBox = q('#tw-why-box');
  if (whyBox) whyBox.textContent = sug.why || '';
  const structureBox = q('#tw-structure-summary');
  if (structureBox) {
    structureBox.innerHTML = `<strong>Objetivo:</strong> ${esc(q('#tw-camp-objective')?.value || '')}<br/><strong>Conta:</strong> ${esc(S.campaigns.adAccountName || S.campaigns.adAccountId || '—')}<br/><strong>Destino sugerido:</strong> ${esc(twObjectiveMeta(q('#tw-camp-objective')?.value || '').destination)}`;
  }

  // Render location chips
  renderTWLocations(sug.location_suggested);

  // Render interest chips with history labels
  renderTWInterests();

  // Historical links as selectable cards
  const linksSection = q('#tw-links-section');
  const linksList = q('#tw-links-list');
  if (TW.links.length && linksList) {
    if (linksSection) linksSection.style.display = '';
    linksList.innerHTML = TW.links.slice(0, 8).map(l =>
      `<div onclick="selectTWLink('${esc(l.url)}')" style="padding:8px 12px;border:1px solid var(--border);border-radius:8px;cursor:pointer;font-size:12px;background:var(--surface)" title="${esc(l.url)}">
        <div style="font-weight:600;font-size:11px;color:var(--text-muted);margin-bottom:2px">${esc(l.ad_name)}</div>
        <div style="color:var(--primary,#6366f1);word-break:break-all">${esc(l.url.substring(0,80))}${l.url.length>80?'…':''}</div>
      </div>`
    ).join('');
    // Pre-fill first link
    if (TW.links[0]?.url && q('#tw-dest-url')) q('#tw-dest-url').value = TW.links[0].url;
  }

  // Forms dropdown
  const formSel = q('#tw-dest-form');
  if (formSel) {
    formSel.innerHTML = '<option value="">Selecione um formulário</option>' +
      TW.forms.map(f => `<option value="${f.id}">${esc(f.name || f.id)}</option>`).join('');
    if (TW.forms[0]?.id) formSel.value = TW.forms[0].id;
  }
  const pixelSel = q('#tw-dest-pixel');
  if (pixelSel) {
    pixelSel.innerHTML = '<option value="">Selecione um pixel</option>' +
      TW.pixels.map(p => `<option value="${esc(p.pixel_id || p.id || '')}">${esc(p.name || p.pixel_id || p.id || '')}</option>`).join('');
    if (TW.pixels[0]) pixelSel.value = TW.pixels[0].pixel_id || TW.pixels[0].id || '';
  }

  // Dest type toggle
  document.querySelectorAll('[name="tw-dest-type"]').forEach(radio => {
    radio.removeEventListener('change', radio._twHandler);
    radio._twHandler = () => {
      syncTWDestinationUI(radio.value);
    };
    radio.addEventListener('change', radio._twHandler);
  });
  q('#tw-camp-objective')?.addEventListener('change', () => syncTWDestinationUI());

  q('#tw-creative-preview').style.display = 'none';
  q('#tw-creative-url').value = '';
  if (TW.links[0]?.url && q('#tw-dest-sales-url')) q('#tw-dest-sales-url').value = TW.links[0].url;
  syncTWDestinationUI(twObjectiveMeta(q('#tw-camp-objective')?.value || '').destination);
  twGoPane('structure');

  q('#tw-step-2').style.display = 'none';
  q('#tw-step-3').style.display = '';
}

function selectTWLink(url) {
  if (q('#tw-dest-url')) q('#tw-dest-url').value = url;
  if (q('#tw-dest-sales-url')) q('#tw-dest-sales-url').value = url;
  q('#tw-dest-url-radio').checked = true;
  syncTWDestinationUI('url');
  // Highlight selected
  q('#tw-links-list')?.querySelectorAll('div[onclick]').forEach(el => el.style.borderColor = 'var(--border)');
  event?.currentTarget?.style && (event.currentTarget.style.borderColor = 'var(--primary,#6366f1)');
}

function renderTWLocations(suggestedLoc) {
  const el = q('#tw-locations-list');
  if (!el) return;
  if (!TW.locations.length) {
    el.innerHTML = '';
    if (q('#tw-location-custom')) q('#tw-location-custom').value = suggestedLoc || '';
    return;
  }
  // Pre-select AI-suggested location
  const sugLoc = (suggestedLoc || '').toLowerCase();
  TW.locations.forEach(l => { if (sugLoc && (l.name || '').toLowerCase().includes(sugLoc)) TW.selectedLocations.add(l.key); });
  el.innerHTML = TW.locations.slice(0, 12).map(l => {
    const sel = TW.selectedLocations.has(l.key);
    return `<button class="badge ${sel ? 'badge-blue' : 'badge-gray'}" style="cursor:pointer;border:none;padding:5px 10px;font-size:12px" onclick="toggleTWLocation('${l.key}', '${esc(l.name)}', this)">${esc(l.name)}</button>`;
  }).join('');
}

function toggleTWLocation(key, name, el) {
  if (TW.selectedLocations.has(key)) {
    TW.selectedLocations.delete(key);
    el.className = 'badge badge-gray';
  } else {
    TW.selectedLocations.add(key);
    el.className = 'badge badge-blue';
  }
  el.style.cssText = 'cursor:pointer;border:none;padding:5px 10px;font-size:12px';
}

function renderTWInterests() {
  const el = q('#tw-interests-list');
  if (!el) return;
  const histIds = new Set((TW.interests).filter(i => i.from_history).map(i => i.id || i.name));
  el.innerHTML = TW.interests.slice(0, 25).map(i => {
    const key = (i.id || i.name) + ':' + i.name;
    const selected = TW.selectedInterests.has(key);
    const fromHist = i.from_history || histIds.has(i.id);
    const aud = i.audience_size_upper_bound ? ` ${formatNum(Math.round(i.audience_size_upper_bound/1000))}k` : '';
    return `<button class="badge ${selected ? 'badge-blue' : 'badge-gray'}" style="cursor:pointer;border:none;padding:5px 10px;font-size:12px" onclick="toggleTWInterest('${key}', this)" title="${fromHist?'Já usado na conta':'Sugestão Meta'}">${fromHist?'✅ ':''}${esc(i.name)}${aud}</button>`;
  }).join('');
}

function toggleTWInterest(key, el) {
  if (TW.selectedInterests.has(key)) { TW.selectedInterests.delete(key); el.className = 'badge badge-gray'; }
  else { TW.selectedInterests.add(key); el.className = 'badge badge-blue'; }
  el.style.cssText = 'cursor:pointer;border:none;padding:5px 10px;font-size:12px';
}

async function searchTWInterest(q_val) {
  if (!q_val || q_val.length < 3) { q('#tw-interest-search-results').innerHTML = ''; return; }
  const r = await api(`/meta/interest-search?q=${encodeURIComponent(q_val)}&ad_account_id=${encodeURIComponent(S.campaigns.adAccountId)}`);
  const el = q('#tw-interest-search-results');
  if (!el || !r.ok) return;
  (r.interests || []).filter(i => !TW.interests.find(x => x.id === i.id)).forEach(i => TW.interests.push(i));
  el.innerHTML = (r.interests || []).map(i => {
    const key = i.id + ':' + i.name;
    const sel = TW.selectedInterests.has(key);
    return `<button class="badge ${sel ? 'badge-blue' : 'badge-gray'}" style="cursor:pointer;border:none;padding:5px 10px;font-size:12px" onclick="toggleTWInterest('${key}', this);renderTWInterests()">${esc(i.name)}</button>`;
  }).join('');
}

async function generateTWCreative() {
  const btn = q('#btn-tw-creative');
  if (btn) { btn.textContent = '...'; btn.disabled = true; }
  const product = q('#tw-product')?.value || q('#tw-camp-name')?.value || 'produto';
  const headline = q('#tw-headline')?.value || '';
  const prompt = `Arte para anúncio no Instagram 1:1. Produto: ${product}. Headline: ${headline}. ${S.brandProfile?.visual_style || ''}`;
  const r = await post('/panel/ad-builder-generate-image', {
    image_prompt: prompt,
    page_id: S.client?.page_id || '',
    item_type: 'ad_creative',
  });
  if (btn) { btn.textContent = '🎨 Gerar criativo'; btn.disabled = false; }
  if (r.ok && (r.public_url || r.image?.images?.[0])) {
    const url = r.public_url || r.image?.images?.[0] || '';
    q('#tw-creative-url').value = url;
    const img = q('#tw-creative-img');
    const prev = q('#tw-creative-preview');
    if (img && prev) { img.src = url; prev.style.display = ''; }
  } else {
    alert('Erro ao gerar criativo: ' + (r.error || 'desconhecido'));
  }
}

async function createTrafficWizardDraft() {
  const btn = q('#btn-tw-create');
  if (btn) { btn.textContent = 'Criando...'; btn.disabled = true; }
  const objective = q('#tw-camp-objective')?.value || 'OUTCOME_LEADS';
  const destType = document.querySelector('[name="tw-dest-type"]:checked')?.value || twObjectiveMeta(objective).destination;
  const link = destType === 'url' ? (q('#tw-dest-url')?.value || '').trim() : destType === 'pixel' ? (q('#tw-dest-sales-url')?.value || '').trim() : '';
  const formId = destType === 'form' ? (q('#tw-dest-form')?.value || '') : '';
  const pixelId = destType === 'pixel' ? (q('#tw-dest-pixel')?.value || '') : '';
  const objectiveCfg = twObjectiveMeta(objective);
  const interests = [...TW.selectedInterests].map(k => {
    const parts = k.split(':'); const id = parts[0]; const name = parts.slice(1).join(':');
    return { id, name };
  });
  // Build locations from selected chips + custom field
  const selectedLocs = [...TW.selectedLocations];
  const customLoc = (q('#tw-location-custom')?.value || '').trim();
  let geoLocations = { countries: [{ country_code: 'BR' }] };
  if (selectedLocs.length) {
    // Reconstruct geo_locations grouping by type
    const byType = {};
    selectedLocs.forEach(key => {
      const loc = TW.locations.find(l => l.key === key);
      if (!loc) return;
      const t = loc.type || 'regions';
      if (!byType[t]) byType[t] = [];
      const entry = t === 'countries' ? { country_code: key } : { key };
      byType[t].push(entry);
    });
    if (Object.keys(byType).length) geoLocations = byType;
  } else if (customLoc) {
    geoLocations = { countries: [{ name: customLoc }] };
  }

  const r = await post('/meta/ad-drafts/create-campaign', {
    ad_account_id: S.campaigns.adAccountId,
    campaign_name: (q('#tw-camp-name')?.value || '').trim() || 'Campanha IA',
    adset_name: 'Público IA',
    daily_budget: String(Math.round(Number(q('#tw-camp-budget')?.value || 50) * 100)),
    objective,
    page_id: S.client?.page_id || '',
    instagram_actor_id: S.client?.ig_user_id || '',
    creative_name: ((q('#tw-camp-name')?.value || '').trim() || 'Campanha IA') + ' · Criativo',
    ad_name: ((q('#tw-camp-name')?.value || '').trim() || 'Campanha IA') + ' · Ad 1',
    message: (q('#tw-primary-text')?.value || '').trim(),
    call_to_action_type: objectiveCfg.cta,
    link: link,
    image_url: q('#tw-creative-url')?.value || '',
    optimization_goal: objectiveCfg.optimization_goal,
    billing_event: objectiveCfg.billing_event,
    promoted_object: destType === 'form' && formId ? { page_id: S.client?.page_id || '', lead_ads_custom_conversion: formId } :
      destType === 'pixel' && pixelId ? { pixel_id: pixelId, custom_event_type: 'PURCHASE' } : undefined,
    targeting: {
      age_min: parseInt(q('#tw-age-min')?.value || '25', 10),
      age_max: parseInt(q('#tw-age-max')?.value || '55', 10),
      geo_locations: geoLocations,
      ...(interests.length ? { flexible_spec: [{ interests }] } : {}),
    },
  });
  if (btn) { btn.textContent = 'Criar rascunho'; btn.disabled = false; }
  if (r.ok) {
    closeModal('modal-traffic-wizard');
    showCampaignAlert('success', `Rascunho criado: ${r.campaign?.name || 'nova campanha'}. Veja na aba Rascunhos.`);
    const tabBtn = document.querySelector('#sec-campaigns .tabs-row .tab-btn:nth-child(3)');
    if (tabBtn) switchCampaignTab('drafts', tabBtn);
  } else {
    alert('Erro ao criar: ' + (r.detail || r.error || 'desconhecido'));
  }
}

/* ── AGENTS ────────────────────────────────────────────────── */
async function loadAgents() {
  // Carrega contexto de planejamento (agora dentro de loadContent → tab 'plan')
  if (q('#agents-sub')) q('#agents-sub').textContent = `Conteúdo · ${S.client.name}`;
  if (q('#plan-client-display')) q('#plan-client-display').textContent = S.client.name;
  if (q('#plan-client-display-modal')) q('#plan-client-display-modal').textContent = S.client.name;
  if (!S.brandProfile.brand_name) {
    const r = await api('/panel/brand-profiles');
    if (r.ok) S.brandProfile = (r.profiles||{})[S.client.page_id] || {};
  }
  if (q('#sp-logo-status')) q('#sp-logo-status').textContent = (S.brandProfile?.logo_url || '') ? 'Logo cadastrada pronta para usar' : 'Nenhuma logo cadastrada no momento';
  handleSinglePostImageSourceChange();
  if (!S.plan.length) await loadSavedPlan();
  renderPlanList();
  renderHomeBrandBar();
}

async function loadSavedPlan() {
  const r = await api(`/panel/content-plans?page_id=${S.client.page_id}&limit=1`);
  if (r.ok && r.plans?.length) {
    const plan = r.plans[0];
    S.planId = plan.id;
    S.planMeta = {
      mode: plan.plan_type || 'monthly',
      focus: plan.focus || '',
      title: plan.title || '',
      month_label: plan.month_label || '',
    };
    S.plan = (plan.posts || []).map((p, i) => ({ ...p, _idx: i }));
  }
  await loadClientAIUsage();
}

function openPlanModal() {
  if (!S.client) { openClientModal(); return; }
  q('#plan-client-display').textContent = S.client.name;
  if (q('#plan-client-display-modal')) q('#plan-client-display-modal').textContent = S.client.name;
  q('#plan-modal-alert').innerHTML = '';
  if (q('#plan-mode')) q('#plan-mode').value = S.planMeta.mode || 'monthly';
  openModal('modal-plan');
}

function openSinglePostModal() {
  if (!S.client) { openClientModal(); return; }
  if (q('#sp-logo-status')) q('#sp-logo-status').textContent = 'Usará a logo cadastrada da empresa';
  if (q('#sp-alert')) q('#sp-alert').innerHTML = '';
  syncSinglePostChannelUI();
  openModal('modal-single-post');
}

function syncSinglePostChannelUI() {
  const ig = Boolean(S.client?.instagram_connected);
  const fb = Boolean(S.client?.facebook_connected);
  const igWrap = q('#sp-channel-instagram-wrap');
  const fbWrap = q('#sp-channel-facebook-wrap');
  if (igWrap) igWrap.style.display = ig ? '' : 'none';
  if (fbWrap) fbWrap.style.display = fb ? '' : 'none';
  if (q('#sp-channel-instagram')) q('#sp-channel-instagram').checked = ig;
  if (q('#sp-channel-facebook')) q('#sp-channel-facebook').checked = false;
}

function getSinglePostChannels() {
  const channels = [];
  if (q('#sp-channel-instagram')?.checked) channels.push('instagram');
  if (q('#sp-channel-facebook')?.checked) channels.push('facebook');
  return channels;
}

/** A partir do menu Conteúdo: abre Planejamento e o bloco “+ Conteúdo (post único)”. */
function goToSinglePostPanel() {
  if (!S.client) { openClientModal(); return; }
  goto('planejamento');
  setTimeout(() => openSinglePostModal(), 200);
}

async function generatePlan() {
  setBtnLoading('#btn-gen-plan-confirm', true, 'Gerando...');
  q('#plan-modal-alert').innerHTML = '';
  try {
    const mode = q('#plan-mode')?.value || 'monthly';
    const weeks = safeInt(q('#plan-weeks')?.value, mode === 'single' ? 1 : 4);
    const postsPerWeek = safeInt(q('#plan-ppw')?.value, mode === 'single' ? 1 : 3);
    const r = await post('/panel/agents/generate-plan', {
      page_id: S.client.page_id,
      weeks,
      posts_per_week: postsPerWeek,
      focus: q('#plan-focus').value.trim(),
      mode,
    });
    if (!r.ok) {
      q('#plan-modal-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao gerar plano.');
      return;
    }
    if (!Array.isArray(r.posts) || !r.posts.length) {
      q('#plan-modal-alert').innerHTML = mkAlert('error', 'A IA não retornou itens de plano. Tente novamente ou ajuste o foco.');
      return;
    }
    S.plan = r.posts.map((p, i) => ({ ...p, status: 'pending', _idx: i }));
    S.planId = null;
    S.planMeta = {
      mode: r.mode || mode,
      focus: r.focus || q('#plan-focus').value.trim(),
      title: (r.mode || mode) === 'single' ? `Conteúdo avulso · ${new Date().toLocaleDateString('pt-BR')}` : `Plano mensal · ${new Date().toLocaleDateString('pt-BR',{month:'long',year:'numeric'})}`,
      month_label: new Date().toLocaleDateString('pt-BR',{month:'long',year:'numeric'}),
    };
    S.selected.clear();
    closeModal('modal-plan');
    const saved = await post('/panel/content-plan/save', {
      page_id: S.client.page_id, page_name: S.client.name,
      ig_user_id: S.client.ig_user_id, ig_username: S.client.ig_username,
      posts: S.plan, model: r.model || '',
      focus: S.planMeta.focus,
      title: S.planMeta.title,
      plan_type: S.planMeta.mode,
      month_label: S.planMeta.month_label,
    });
    if (saved.ok) {
      S.planId = saved.plan?.id || null;
      await hydrateCurrentPlanFromBackend();
      await loadClientAIUsage();
      showPlanAlert('success', 'Plano salvo.');
    } else {
      showPlanAlert('error', `Erro ao salvar plano: ${saved.detail || saved.error || 'falha desconhecida'}`);
    }
    renderPlanList();
    if (S.contentTab === 'scripts') loadStoryScripts();
  } catch (e) {
    q('#plan-modal-alert').innerHTML = mkAlert('error', `Falha inesperada ao gerar plano: ${String(e)}`);
  } finally {
    setBtnLoading('#btn-gen-plan-confirm', false, 'Gerar com IA');
  }
}

async function suggestPlanFocus() {
  setBtnLoading('#btn-plan-focus-suggestion', true, 'Sugerindo...');
  try {
    const mode = q('#plan-mode')?.value || 'monthly';
    const r = await api('/panel/agents/generate-plan', { method: 'POST', body: JSON.stringify({
      page_id: S.client.page_id,
      weeks: safeInt(q('#plan-weeks')?.value, mode === 'single' ? 1 : 4),
      posts_per_week: safeInt(q('#plan-ppw')?.value, mode === 'single' ? 1 : 3),
      focus: q('#plan-focus').value.trim(),
      mode,
      suggest_focus: true,
    }), _timeout: 90000 });
    if (!r.ok) { q('#plan-modal-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao sugerir foco.'); return; }
    if (r.focus) q('#plan-focus').value = r.focus;
    q('#plan-modal-alert').innerHTML = mkAlert('success', 'Foco sugerido preenchido. Revise antes de gerar o plano.');
  } catch (e) {
    q('#plan-modal-alert').innerHTML = mkAlert('error', `Falha inesperada ao sugerir foco: ${String(e)}`);
  } finally {
    setBtnLoading('#btn-plan-focus-suggestion', false, 'Gerar sugestão com IA');
  }
}

async function suggestSinglePostFocus() {
  if (!S.client?.page_id) { q('#sp-alert').innerHTML = mkAlert('error', 'Selecione uma empresa.'); return; }
  setBtnLoading('#btn-sp-focus-suggestion', true, 'Sugerindo...');
  const theme = (q('#sp-theme')?.value || '').trim();
  const r = await post('/panel/single-content/suggest-focus', {
    page_id: S.client.page_id,
    theme,
  });
  setBtnLoading('#btn-sp-focus-suggestion', false, 'Sugerir com IA');
  if (!r.ok) { q('#sp-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao sugerir foco.'); return; }
  if (r.image_focus) q('#sp-image-focus').value = r.image_focus;
  q('#sp-alert').innerHTML = mkAlert('success', 'Sugestão preenchida. Ajuste se quiser antes de gerar.');
}

async function hydrateCurrentPlanFromBackend() {
  if (!S.client || !S.planId) return;
  const r = await api(`/panel/content-plans?page_id=${S.client.page_id}&limit=1`);
  const latest = r.ok && r.plans?.length ? r.plans[0] : null;
  if (!latest || latest.id !== S.planId || !Array.isArray(latest.posts) || !latest.posts.length) return;
  S.plan = latest.posts.map((p, i) => ({ ...S.plan[i], ...p, _idx: i }));
}

/* ── PLAN RENDER ───────────────────────────────────────────── */
function renderPlanList() {
  const list = q('#agents-plan-list');
  const empty = q('#agents-plan-empty');
  const resetBtn = q('#btn-reset-plan');
  const saveBtn = q('#btn-save-plan');
  const reviewBar = q('#agents-review-bar');
  const posts = planRenderablePosts();
  renderPlanSummary();
  renderStartGenerationButton();
  if (!posts.length && !planStoryItems().length) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    resetBtn.style.display = 'none';
    if (saveBtn) saveBtn.style.display = 'none';
    reviewBar.classList.add('hidden');
    hideBulkBar();
    return;
  }
  empty.classList.add('hidden');
  resetBtn.style.display = '';
  if (saveBtn) saveBtn.style.display = '';

  list.innerHTML = posts.length ? posts.map(({ item, idx }) => planItemHTML(idx, item)).join('') : '<div class="empty-state"><div class="empty-icon">◌</div><h3>Sem posts de feed neste plano</h3><p>Os roteiros de story ficam na aba Conteúdo → Roteiros.</p></div>';

  const ready = posts.filter(({ item }) => ['has_content','approved'].includes(item.status)).length;
  if (ready > 0) { reviewBar.classList.remove('hidden'); reviewBar.style.display = 'flex'; q('#agents-review-count').textContent = ready; }
  else reviewBar.classList.add('hidden');

  updateBulkBar();
}

function planItemHTML(i, p) {
  const cls = { has_content:'has-content', approved:'approved', rejected:'rejected', error:'rejected' }[p.status] || '';
  const checked = S.selected.has(i) ? 'checked' : '';
  const formatLabel = p.format === 'carousel' ? 'Carrossel' : p.format === 'story_script' ? 'Story' : 'Post estático';
  const validationBadge = p.validation?.container_id ? '<span class="badge badge-blue">Validado IG</span>' : '';
  const costBadge = planItemCostBadge(p);
  return `<div class="plan-item ${cls}" id="plan-item-${i}">
    <input type="checkbox" class="plan-check" ${checked} onchange="toggleSelect(${i},this.checked)"/>
    <div class="plan-num">${i+1}</div>
    <div class="plan-info">
      <div class="plan-title">${esc(p.title)}</div>
      <div class="plan-meta">${esc(p.suggested_date||'')} ${p.suggested_time||''} · ${esc(p.theme||'')} · ${formatLabel}</div>
      ${validationBadge}${costBadge}
    </div>
    <div class="plan-actions" id="plan-actions-${i}">${planActions(i, p)}</div>
  </div>`;
}

function planItemCostBadge(p) {
  const stats = S.aiUsage?.byPost?.[p.id];
  if (!stats || !(Number(stats.cost_usd || 0) > 0 || Number(stats.tokens || 0) > 0)) return '';
  return `<div style="margin-top:6px;font-size:11px;color:var(--text-muted)">IA: ${stats.tokens ? `${formatNum(stats.tokens)} tokens` : '0 tokens'}${stats.cost_usd ? ` · US$ ${Number(stats.cost_usd).toFixed(4)}` : ''}</div>`;
}

function planActions(i, p) {
  const spin = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div>';
  if (p.status==='generating') return spin;
  if (p.status==='has_content') return `<span class="badge badge-green">Pronto</span><button class="btn btn-outline btn-sm" onclick="reviewSingle(${i})">Ver preview</button>`;
  if (p.status==='approved') return `<span class="badge badge-blue">Aprovado</span><button class="btn btn-ghost btn-sm" onclick="reviewSingle(${i})">Ver preview</button>`;
  if (p.status==='rejected') return `<span class="badge badge-red">Reprovado</span><button class="btn btn-ghost btn-sm" onclick="generateSingleContent(${i})">Regenerar</button>`;
  if (p.status==='error') return `<span class="badge badge-red" title="${esc(p._error||'')}">Erro</span><button class="btn btn-ghost btn-sm" onclick="generateSingleContent(${i})">Tentar novamente</button>`;
  return `<span class="badge badge-gray">Pendente</span><button class="btn btn-ghost btn-sm" onclick="generateSingleContent(${i})">Gerar</button>`;
}

function updatePlanItemDOM(idx) {
  const item = S.plan[idx];
  if (!item) return;
  const row = q(`#plan-item-${idx}`);
  if (!row) { renderPlanList(); return; }
  const cls = { has_content:'has-content', approved:'approved', rejected:'rejected', error:'rejected' }[item.status] || '';
  row.className = `plan-item ${cls}`;
  const actEl = q(`#plan-actions-${idx}`);
  if (actEl) actEl.innerHTML = planActions(idx, item);
}

/* ── BULK SELECT ───────────────────────────────────────────── */
function toggleSelect(idx, checked) {
  if (checked) S.selected.add(idx);
  else S.selected.delete(idx);
  updateBulkBar();
}
function selectAll() {
  planRenderablePosts().forEach(({ idx }) => S.selected.add(idx));
  document.querySelectorAll('.plan-check').forEach(c => c.checked = true);
  updateBulkBar();
}
function clearSelection() {
  S.selected.clear();
  document.querySelectorAll('.plan-check').forEach(c => c.checked = false);
  updateBulkBar();
}
function updateBulkBar() {
  const bar = q('#bulk-action-bar');
  if (!bar) return;
  const n = S.selected.size;
  if (n === 0) { bar.classList.remove('open'); return; }
  bar.classList.add('open');
  q('#bulk-count').textContent = `${n} selecionado${n>1?'s':''}`;
}
function hideBulkBar() { q('#bulk-action-bar')?.classList.remove('open'); }

async function bulkGenerate() {
  const idxs = [...S.selected].filter(i => ['pending','error'].includes(S.plan[i]?.status));
  if (!idxs.length) { alert('Selecione posts pendentes para gerar.'); return; }
  clearSelection();
  for (const i of idxs) await generateSingleContent(i);
}
async function bulkRegenerate() {
  const idxs = [...S.selected];
  clearSelection();
  for (const i of idxs) { S.plan[i].status = 'pending'; await generateSingleContent(i); }
}
async function bulkApprove() {
  const idxs = [...S.selected].filter(i => S.plan[i]?.status === 'has_content');
  for (const i of idxs) { S.plan[i].status = 'approved'; if (!['carousel','story_script'].includes(S.plan[i].format)) await schedulePost(S.plan[i]); updatePlanItemDOM(i); savePlanPostUpdate(i); }
  clearSelection(); renderPlanList();
}
function bulkReject() {
  const idxs = [...S.selected];
  for (const i of idxs) { S.plan[i].status = 'rejected'; updatePlanItemDOM(i); savePlanPostUpdate(i); }
  clearSelection(); renderPlanList();
}

/* ── GENERATION ────────────────────────────────────────────── */
function resetPlan() {
  if (!confirm('Criar um novo plano? O atual será mantido no histórico.')) return;
  S.plan = []; S.planId = null; S.selected.clear();
  renderPlanList();
}

async function generateAllContent() {
  for (const { idx, item } of planRenderablePosts()) {
    if (item.status === 'pending') await generateSingleContent(idx);
  }
  // Final save after all content generated
  if (S.planId) await savePlanToBackend();
}

async function startPlanGeneration() {
  await generateAllContent();
  renderStartGenerationButton();
}

async function generateSingleContent(idx) {
  const item = S.plan[idx];
  if (!item || item.status === 'generating') return;
  if (item.format === 'story_script') {
    item.status = 'has_content';
    updatePlanItemDOM(idx);
    await savePlanPostUpdate(idx);
    return;
  }

  item.status = 'generating';
  item._error = '';
  updatePlanItemDOM(idx);

  if (!S.brandProfile.brand_name) {
    const r = await api('/panel/brand-profiles');
    if (r.ok) S.brandProfile = (r.profiles||{})[S.client.page_id] || {};
  }

  // ── STEP 1: Gerar legenda primeiro ───────────────────────
  const profile = S.brandProfile;
  const copyBriefing = [
    `Marca: ${profile.brand_name || S.client.name}`,
    `Tom: ${profile.tone || 'profissional'}`,
    `Público: ${profile.target_audience || ''}`,
    `Tema: ${item.theme}`,
    `Briefing: ${item.brief || item.title}`,
    `CTA: ${item.cta || 'Saiba mais'}`,
    `Hashtag tema: ${item.hashtag_theme || ''}`,
    profile.best_offer ? `Oferta: ${profile.best_offer}` : '',
    profile.key_products ? `Produtos: ${profile.key_products}` : '',
  ].filter(Boolean).join('\n');

  const copyR = await post('/meta/ai-copy', {
    briefing: copyBriefing,
    page_id: S.client.page_id,
    plan_id: S.planId || '',
    post_id: item.id || '',
    item_type: item.format || 'static',
    art_direction: {
      colors: Array.isArray(profile.colors) ? profile.colors.join(', ') : (profile.colors||''),
      visual_style: profile.visual_style || '',
      font_preference: profile.font_preference || '',
      reference_image_url: profile.reference_image_url || '',
      reference_style_prompt: profile.reference_style_prompt || '',
      use_reference_style: !!profile.use_reference_style,
      references: normalizeVisualReferences(profile.visual_references || []).filter(r => r.use_for_style).map(r => r.url).filter(Boolean),
    },
  });

  if (!copyR.ok || !copyR.copy) {
    item.status = 'error';
    item._error = copyR.detail || copyR.error || 'Falha ao gerar legenda';
    updatePlanItemDOM(idx);
    return;
  }
  item.caption = copyR.copy;
  if (copyR.title) item.title = copyR.title;
  if (copyR.subtitle) item.subtitle = copyR.subtitle;
  if (copyR.image_prompt) item.image_prompt = copyR.image_prompt;
  // Show caption in plan item meta immediately
  const metaEl = q(`#plan-item-${idx} .plan-meta`);
  if (metaEl) metaEl.title = item.caption.substring(0, 100);

  // ── STEP 2: Gerar imagem(ns) ─────────────────────────────
  if (item.format === 'carousel') {
    const slides = Array.isArray(item.carousel_slides) && item.carousel_slides.length ? item.carousel_slides : [item.title, item.theme, item.cta || 'Saiba mais'];
    item.image_urls = [];
    item.image_prompts = [];
    const trimmedSlides = slides.slice(0, 6);
    for (let slideIdx = 0; slideIdx < trimmedSlides.length; slideIdx += 1) {
      const slide = trimmedSlides[slideIdx];
      const imagePrompt = buildImagePrompt({
        ...item,
        title: slide,
        brief: `${item.brief || item.title}. Lâmina ${slideIdx + 1} do carrossel: ${slide}`,
        _slideIndex: slideIdx,
        _slideCount: trimmedSlides.length,
      }, profile, copyR.image_prompt);
      item.image_prompts.push(imagePrompt);
      const imgR = await post('/panel/ad-builder-generate-image', { image_prompt: imagePrompt, page_id: S.client.page_id, plan_id: S.planId || '', post_id: item.id || '', item_type: 'carousel' });
      if (imgR.ok && (imgR.public_url || imgR.image?.images?.[0])) item.image_urls.push(imgR.public_url || imgR.image?.images?.[0] || '');
    }
    item.image_url = item.image_urls[0] || '';
  } else {
    const imagePrompt = buildImagePrompt(item, profile, copyR.image_prompt);
    item.image_prompts = [imagePrompt];
    const imgR = await post('/panel/ad-builder-generate-image', { image_prompt: imagePrompt, page_id: S.client.page_id, plan_id: S.planId || '', post_id: item.id || '', item_type: item.format || 'static' });
    if (imgR.ok && (imgR.public_url || imgR.image?.images?.[0])) item.image_url = imgR.public_url || imgR.image?.images?.[0] || '';
    else item.image_url = '';
  }

  // ── STEP 3: Validar criação de mídia no Instagram ────────
  const validationPayload = {
    page_id: S.client.page_id,
    format: item.format || 'static',
    caption: item.caption || '',
    image_url: item.image_url || '',
    image_urls: item.image_urls || [],
  };
  const validation = await post('/panel/content-plan/validate-media', validationPayload);
  if (!validation.ok) {
    item.status = 'error';
    item._error = validation.detail || validation.error || 'Falha ao validar mídia no Instagram';
    item.validation = {};
    updatePlanItemDOM(idx);
    await savePlanPostUpdate(idx);
    return;
  }
  item.validation = validation.validation || {};
  item.status = 'has_content';
  await loadClientAIUsage();
  updatePlanItemDOM(idx);
  savePlanPostUpdate(idx);

  // Update review bar
  const ready = S.plan.filter(p => ['has_content','approved'].includes(p.status)).length;
  const bar = q('#agents-review-bar');
  if (ready > 0 && bar) { bar.classList.remove('hidden'); bar.style.display = 'flex'; q('#agents-review-count').textContent = ready; }
  renderStartGenerationButton();
  renderPlanSummary();
}

function buildImagePrompt(item, profile, aiPrompt) {
  const brandName = profile.brand_name || S.client?.name || '';
  const colors = Array.isArray(profile.colors) ? profile.colors.join(', ') : (profile.colors||'');
  const visual = profile.visual_style || 'moderno e profissional';
  const fontPreference = profile.font_preference || '';
  const refStyle = profile.use_reference_style ? (profile.reference_style_prompt || '') : '';
  const hasLogo = !!(profile.logo_url || profile.logo_path);
  const logoRule = hasLogo
    ? '\nLogo: NÃO gerar, recriar, desenhar, sugerir ou simular nenhuma logo, símbolo de marca, assinatura ou watermark. A logo real em PNG será aplicada depois como overlay externo.'
    : '\nLogo: não inventar, desenhar ou sugerir logotipos, marcas, assinaturas ou watermarks.';
  const slideIndex = Number.isFinite(item._slideIndex) ? item._slideIndex : null;
  const slideCount = Number.isFinite(item._slideCount) ? item._slideCount : null;
  const isCarousel = item.format === 'carousel' && slideIndex !== null && slideCount !== null;
  if (isCarousel) {
    const stageBySlide = ['HOOK', 'CONTEXTO', 'EXPLICAÇÃO', 'APROFUNDAMENTO', 'BENEFÍCIO', 'CTA FINAL'];
    const slideStage = stageBySlide[Math.min(slideIndex, stageBySlide.length - 1)];
    const slideText = item.title || item.theme || '';
    const promptBase = aiPrompt && aiPrompt.length > 40 ? aiPrompt : item.brief || item.theme || '';
    return `Crie a imagem da lâmina ${slideIndex + 1} de ${slideCount} de um carrossel para Instagram, formato 1:1 (1080x1080), com estilo moderno, tecnológico e minimalista, adaptado ao nicho "${item.theme || brandName}".

Objetivo desta lâmina:
- Papel narrativo: ${slideStage}
- Texto principal desta lâmina: "${slideText}"
- Máximo de 8 a 12 palavras visíveis na arte
- O texto deve aparecer de forma legível, com hierarquia clara e composição limpa

Direção visual consistente em todo o carrossel:
- Marca: ${brandName}
- Paleta principal: ${colors || 'tons escuros com contraste premium'}
- Estilo visual: ${visual}
- Tipografia desejada: ${fontPreference || 'moderna, sans-serif e legível'}
- Iluminação: suave, premium, alto contraste
- Mesma identidade visual, mesma direção de luz, mesmos elementos de apoio e sensação de progressão entre todas as lâminas
- Os elementos visuais devem evoluir de uma lâmina para outra, sem parecer imagens soltas
${refStyle ? `- Seguir este padrão visual sintetizado das referências da marca: ${refStyle}` : ''}

Instruções específicas desta lâmina:
- Incorporar EXATAMENTE este texto principal na arte: "${slideText}"
- Se houver apoio visual de subtítulo, usar no máximo uma linha curta baseada em: "${item.subtitle || item.theme || ''}"
- Base criativa: ${promptBase}
- Evitar excesso de texto, poluição visual ou blocos longos
- Tipografia moderna, sans-serif, clean e muito legível
- Reservar área completamente limpa no canto inferior ESQUERDO — sem texto, ícone, sombra ou qualquer elemento. A logo real será aplicada como overlay externo depois.
${slideIndex < slideCount - 1
  ? '- Incluir um micro CTA visual no lado direito com o texto "Arraste →", discreto mas perceptível'
  : '- Esta é a última lâmina; não incluir seta, nem CTA de arraste'}
${logoRule}

Restrições:
- Não parecer uma imagem independente; deve parecer parte da mesma sequência
- Não inventar textos extras além do necessário
- Não usar texto pequeno demais
- Não quebrar a consistência visual do carrossel
- Não gerar logos, marcas, logotipos, assinaturas ou watermarks

--ar 1:1 --style raw`;
  }
  if (aiPrompt && aiPrompt.length > 40) return aiPrompt;
  return `Crie uma arte para Instagram no formato 1:1 (1080x1080), com estilo ${visual}, adaptado ao nicho e ao conteúdo do post.

Marca: ${brandName}
Tema: ${item.theme}
${item.brief ? `Direção criativa: ${item.brief}` : ''}
${colors ? `Cores: ${colors}` : ''}
${fontPreference ? `Tipografia desejada: ${fontPreference}` : ''}
${refStyle ? `Referência de estilo prioritária: ${refStyle}` : ''}

Conteúdo:
- Título: "${item.title}"
- Subtítulo: "${item.subtitle || item.theme || ''}"
- CTA: "${item.cta || 'Saiba mais'}"
- Reservar área completamente limpa no canto inferior ESQUERDO — sem texto, ícone, sombra ou qualquer elemento. A logo real será aplicada como overlay externo depois.
${logoRule}

Regras:
- Tipografia clean, moderna, alto contraste
- Layout limpo, sem distorção de texto
- Hierarquia: subtítulo → título → CTA
- Ultra realistic, soft lighting, cinematic
- Não gerar logos, marcas, logotipos, assinaturas ou watermarks

--ar 1:1 --style raw`;
}

async function savePlanPostUpdate(idx) {
  if (!S.planId) return;
  const item = S.plan[idx];
  if (!item) return;
  const res = await post('/panel/content-plan/update-post', {
    post_id: item.id,
    plan_id: S.planId,
    page_id: S.client.page_id,
    caption: item.caption || '',
    image_url: item.image_url || '',
    status: item.status,
    format: item.format || 'static',
    image_prompt: item.image_prompt || '',
    image_prompts: item.image_prompts || [],
    story_script: item.story_script || [],
    carousel_slides: item.carousel_slides || [],
    image_urls: item.image_urls || [],
    validation: item.validation || {},
  });
  if (!res.ok) showPlanAlert('error', `Erro ao atualizar post do plano: ${res.detail || res.error || 'falha desconhecida'}`);
}

async function savePlanToBackend() {
  if (!S.client || !S.plan.length) return;
  const saved = await post('/panel/content-plan/save', {
    plan_id: S.planId || undefined,
    page_id: S.client.page_id, page_name: S.client.name,
    ig_user_id: S.client.ig_user_id, ig_username: S.client.ig_username,
    posts: S.plan,
    focus: S.planMeta.focus || '',
    title: S.planMeta.title || '',
    plan_type: S.planMeta.mode || 'monthly',
    month_label: S.planMeta.month_label || '',
  });
  if (saved.ok) {
    S.planId = saved.plan?.id || S.planId;
    await loadClientAIUsage();
    showPlanAlert('success', 'Plano salvo.');
  } else {
    showPlanAlert('error', `Erro ao salvar plano: ${saved.detail || saved.error || 'falha desconhecida'}`);
  }
}

async function saveCurrentPlan() {
  if (!S.plan.length) return;
  const btn = q('#btn-save-plan');
  if (btn) setBtnLoading('#btn-save-plan', true, 'Salvando...');
  await savePlanToBackend();
  if (btn) setBtnLoading('#btn-save-plan', false, 'Salvar plano');
}

async function loadClientAIUsage() {
  if (!S.client?.page_id) return;
  const r = await api(`/panel/ai/usage-summary?page_id=${S.client.page_id}&limit=2000`);
  if (!r.ok) return;
  S.aiUsage = {
    byPost: r.by_post || {},
    byOperation: r.by_operation || {},
    summary: r.summary || {},
  };
}

function showPlanAlert(type, msg) {
  const el = q('#agents-plan-alert');
  if (!el) return;
  el.innerHTML = mkAlert(type, msg);
  setTimeout(() => { if (q('#agents-plan-alert')) q('#agents-plan-alert').innerHTML = ''; }, 5000);
}

/* ── REVIEW MODAL ──────────────────────────────────────────── */
function openReviewModal() {
  const idxs = reviewableIdxs();
  if (!idxs.length) return;
  // Start from first un-reviewed
  const firstPending = idxs.find(i => S.plan[i].status === 'has_content');
  S.reviewIdx = firstPending ?? idxs[0];
  S.reviewCarouselIdx = 0;
  renderReviewPost();
  openModal('modal-review');
}
function reviewSingle(idx) { S.reviewIdx = idx; S.reviewCarouselIdx = 0; renderReviewPost(); openModal('modal-review'); }
function reviewableIdxs() { return S.plan.reduce((a,p,i) => { if (p.format !== 'story_script' && ['has_content','approved','rejected'].includes(p.status)) a.push(i); return a; }, []); }

function reviewMediaList(item) {
  if (!item) return [];
  if (item.format === 'carousel' && Array.isArray(item.image_urls) && item.image_urls.length) return item.image_urls.filter(Boolean);
  return item.image_url ? [item.image_url] : [];
}

function ensureReviewCarouselControls() {
  let el = q('#review-carousel-controls');
  if (el) return el;
  const preview = q('#review-preview');
  if (!preview) return null;
  el = document.createElement('div');
  el.id = 'review-carousel-controls';
  el.style.cssText = 'display:none;align-items:center;justify-content:center;gap:8px;margin-top:10px;flex-wrap:wrap';
  el.innerHTML = `
    <button class="btn btn-outline btn-sm" onclick="reviewCarouselNav(-1)">←</button>
    <span id="review-carousel-counter" class="badge badge-gray">1/1</span>
    <button class="btn btn-outline btn-sm" onclick="reviewCarouselNav(1)">→</button>
    <button class="btn btn-ghost btn-sm" id="btn-regen-slide" onclick="reviewRegenSlide()" title="Regenerar só esta lâmina">↺ Esta lâmina</button>
  `;
  preview.appendChild(el);
  return el;
}

function reviewCarouselNav(dir) {
  const item = S.plan[S.reviewIdx];
  const media = reviewMediaList(item);
  if (media.length <= 1) return;
  S.reviewCarouselIdx = Math.max(0, Math.min(media.length - 1, S.reviewCarouselIdx + dir));
  renderReviewPost();
}

async function reviewRegenSlide() {
  const item = S.plan[S.reviewIdx];
  if (!item || item.format !== 'carousel') return;
  const slideIdx = S.reviewCarouselIdx;
  const slides = Array.isArray(item.carousel_slides) && item.carousel_slides.length
    ? item.carousel_slides
    : [item.title, item.theme, item.cta || 'Saiba mais'];
  const slideText = slides[slideIdx] || item.title || '';
  const profile = S.brandProfile;
  const btn = q('#btn-regen-slide');
  if (btn) { btn.textContent = '...'; btn.disabled = true; }
  const imagePrompt = buildImagePrompt({
    ...item,
    title: slideText,
    brief: `${item.brief || item.title}. Lâmina ${slideIdx + 1} do carrossel: ${slideText}`,
    _slideIndex: slideIdx,
    _slideCount: slides.length,
  }, profile, item.image_prompts?.[slideIdx] || '');
  const imgR = await post('/panel/ad-builder-generate-image', {
    image_prompt: imagePrompt,
    page_id: S.client.page_id,
    plan_id: S.planId || '',
    post_id: item.id || '',
    item_type: 'carousel',
  });
  if (btn) { btn.textContent = '↺ Esta lâmina'; btn.disabled = false; }
  if (imgR.ok && (imgR.public_url || imgR.image?.images?.[0])) {
    const newUrl = imgR.public_url || imgR.image?.images?.[0] || '';
    if (!Array.isArray(item.image_urls)) item.image_urls = [];
    item.image_urls[slideIdx] = newUrl;
    if (Array.isArray(item.image_prompts)) item.image_prompts[slideIdx] = imagePrompt;
    if (slideIdx === 0) item.image_url = newUrl;
    renderReviewPost();
    savePlanPostUpdate(S.reviewIdx);
  }
}

function renderReviewPost() {
  const idxs = reviewableIdxs();
  const pos = idxs.indexOf(S.reviewIdx) + 1;
  q('#review-counter').textContent = `Post ${pos} de ${idxs.length}`;
  const item = S.plan[S.reviewIdx];
  if (!item) return;
  const media = reviewMediaList(item);
  if (S.reviewCarouselIdx >= media.length) S.reviewCarouselIdx = 0;
  const src = media[S.reviewCarouselIdx] || item.image_url || '';
  const cap = item.caption || '';
  const name = S.client?.name || 'Página';
  const igUser = S.client?.ig_username ? '@'+S.client.ig_username : name;
  q('#ig-username').textContent = igUser;
  setImgSrc('#ig-img', src); q('#ig-cap-name').textContent = igUser; q('#ig-cap-text').textContent = cap.substring(0,200);
  q('#fb-av').textContent = name[0]?.toUpperCase()||'P'; q('#fb-name').textContent = name;
  q('#fb-cap').textContent = cap.substring(0,300); setImgSrc('#fb-img', src);
  q('#li-av').textContent = name[0]?.toUpperCase()||'P'; q('#li-name').textContent = name;
  q('#li-cap').textContent = cap.substring(0,300); setImgSrc('#li-img', src);
  const dateVal = item.suggested_date || '';
  const timeVal = item.suggested_time || '19:00';
  const dateInput = q('#review-date-input');
  const timeInput = q('#review-time-input');
  if (dateInput) dateInput.value = dateVal;
  if (timeInput) timeInput.value = timeVal;
  const scheduledLabel = q('#ig-scheduled-at');
  if (scheduledLabel) {
    scheduledLabel.textContent = dateVal ? `Agendado: ${fmtDateLong(dateVal)} às ${timeVal}` : '';
  }
  q('#review-theme').textContent = item.theme || item.title || '';
  q('#review-caption').value = cap;
  // Show status badge in modal
  const statusEl = q('#review-status-badge');
  if (statusEl) {
    const slideBadge = item.format === 'carousel' && media.length > 1 ? `<span class="badge badge-yellow">Lâmina ${S.reviewCarouselIdx + 1} de ${media.length}</span>` : '';
    const stateBadge = item.status === 'approved' ? '<span class="badge badge-blue">Aprovado</span>' : item.status === 'rejected' ? '<span class="badge badge-red">Reprovado</span>' : '';
    statusEl.innerHTML = `${stateBadge} ${slideBadge}`.trim();
  }
  const controls = ensureReviewCarouselControls();
  if (controls) {
    controls.style.display = item.format === 'carousel' && media.length > 1 ? 'flex' : 'none';
    const counter = q('#review-carousel-counter');
    if (counter) counter.textContent = `${S.reviewCarouselIdx + 1}/${Math.max(1, media.length)}`;
  }
}

function setImgSrc(sel, src) { const el = q(sel); if (!el) return; el.src = src; }

function switchPlatform(platform, el) {
  S.reviewPlatform = platform;
  document.querySelectorAll('.ptab').forEach(t => t.classList.remove('active'));
  if (el) el.classList.add('active');
  ['instagram','facebook','linkedin'].forEach(p => { q(`#preview-${p}`).style.display = p === platform ? '' : 'none'; });
}

function reviewNav(dir) {
  const idxs = reviewableIdxs();
  const cur = idxs.indexOf(S.reviewIdx);
  const next = cur + dir;
  if (next >= 0 && next < idxs.length) {
    if (S.plan[S.reviewIdx]) _syncReviewDateTime(S.plan[S.reviewIdx]);
    S.reviewIdx = idxs[next];
    S.reviewCarouselIdx = 0;
    renderReviewPost();
  }
}

function _syncReviewDateTime(item) {
  if (!item) return;
  item.caption = (q('#review-caption')?.value || item.caption || '').trim();
  const d = q('#review-date-input')?.value || '';
  const t = q('#review-time-input')?.value || '';
  if (d) item.suggested_date = d;
  if (t) item.suggested_time = t;
}

async function reviewAction(action) {
  const item = S.plan[S.reviewIdx];
  if (!item) return;
  _syncReviewDateTime(item);
  item.status = action;
  if (action === 'approved' && !['carousel','story_script'].includes(item.format)) await schedulePost(item);
  updatePlanItemDOM(S.reviewIdx);
  savePlanPostUpdate(S.reviewIdx);
  renderPlanList();
  const remaining = reviewableIdxs().filter(i => S.plan[i].status === 'has_content');
  if (remaining.length > 0) { S.reviewIdx = remaining[0]; S.reviewCarouselIdx = 0; renderReviewPost(); }
  else closeModal('modal-review');
}

async function reviewPostNow() {
  const item = S.plan[S.reviewIdx];
  if (!item) return;
  _syncReviewDateTime(item);
  if (!item.image_url) { alert('Post sem imagem — gere a imagem primeiro.'); return; }
  if (!S.client?.ig_user_id || !S.client?.access_token) {
    const page = S.pages.find(p => String(p.id) === String(S.client.page_id));
    if (page) { S.client.access_token = page.access_token || ''; S.client.ig_user_id = S.client.ig_user_id || page.instagram_business_account?.id || ''; }
  }
  if (!S.client?.ig_user_id || !S.client?.access_token) { alert('Conta do Instagram não conectada.'); return; }
  const r = await post('/meta/instagram/post', {
    page_id: S.client.page_id,
    ig_user_id: S.client.ig_user_id,
    access_token: S.client.access_token,
    image_url: item.image_url,
    caption: item.caption || '',
    publish_now: true,
  });
  if (r.ok) {
    item.status = 'approved';
    updatePlanItemDOM(S.reviewIdx);
    savePlanPostUpdate(S.reviewIdx);
    renderPlanList();
    const remaining = reviewableIdxs().filter(i => S.plan[i].status === 'has_content');
    if (remaining.length > 0) { S.reviewIdx = remaining[0]; S.reviewCarouselIdx = 0; renderReviewPost(); }
    else closeModal('modal-review');
    showAlert('agents-plan-alert', 'Post publicado no Instagram!', 'success');
  } else {
    alert('Erro ao publicar: ' + (r.detail || r.error || 'erro desconhecido'));
  }
}

async function reviewRegen() {
  const item = S.plan[S.reviewIdx];
  if (!item) return;
  item.caption = q('#review-caption').value;
  q('#review-gen-loading').classList.remove('hidden');
  item.status = 'pending';
  await generateSingleContent(S.reviewIdx);
  q('#review-gen-loading').classList.add('hidden');
  renderReviewPost();
}

async function schedulePost(item) {
  if (!S.client || !item.caption) return;
  if (!S.client.access_token) {
    const page = S.pages.find(p => String(p.id) === String(S.client.page_id));
    if (page) { S.client.access_token = page.access_token||''; S.client.ig_user_id = S.client.ig_user_id || page.instagram_business_account?.id||''; }
  }
  if (!S.client.ig_user_id || !S.client.access_token) return;
  const dt = (item.suggested_date||'') + 'T' + (item.suggested_time||'19:00') + ':00';
  const scheduled_at = Math.floor(new Date(dt).getTime()/1000) || Math.floor(Date.now()/1000 + 3600);
  const r = await post('/schedule/post/add', {
    ig_user_id: S.client.ig_user_id, page_id: S.client.page_id,
    page_name: S.client.name, ig_username: S.client.ig_username,
    access_token: S.client.access_token,
    image_url: item.image_url||'', caption: item.caption,
    scheduled_at, source: 'agents_plan',
  });
  return r;
}

/* ── CONTENT ───────────────────────────────────────────────── */
async function loadContent() {
  // Inicializa contexto de planejamento sempre que entra em Conteúdo
  await loadAgents();
  const loaders = { plan: () => {}, scheduled: loadScheduledPosts, published: loadPublishedPosts, drafts: loadDrafts, gallery: loadContentGallery, calendar: loadCalendar, plans: loadContentPlans, scripts: loadStoryScripts };
  loaders[S.contentTab || 'plan']?.();
}

function switchContentTab(tab, el) {
  S.contentTab = tab;
  document.querySelectorAll('#sec-content .tab-btn').forEach(b => b.classList.remove('active'));
  if (el) el.classList.add('active');
  document.querySelectorAll('#sec-content .tab-panel').forEach(p => p.classList.remove('active'));
  q(`#content-tab-${tab}`)?.classList.add('active');
  loadContent();
}

async function loadScheduledPosts() {
  const r = await api(`/schedule/posts?page_id=${S.client.page_id}&status=pending`);
  const c = q('#content-scheduled-list');
  if (!r.ok||!r.posts?.length) {
    c.innerHTML = `<div class="empty-state"><div class="empty-icon">▦</div><h3>Nenhum post agendado</h3><p>Crie um post único ou um plano e agende a partir dali.</p><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;justify-content:center">
      <button class="btn btn-primary" onclick="goToSinglePostPanel()">Criar conteúdo único</button>
      <button class="btn btn-outline" onclick="goto('content')">Abrir aba Conteúdo</button>
    </div></div>`;
    return;
  }
  c.innerHTML = `<div class="posts-list">${r.posts.map(p=>`
    <div class="post-row">
      ${p.image_url?`<img class="post-thumb" src="${p.image_url}" onerror="this.style.display='none'"/>`:'<div class="post-thumb"></div>'}
      <div class="post-info"><div class="post-name">${esc(p.page_name||'Post')}</div>
      <div class="post-meta">Agendado para ${fmtDate(p.scheduled_at)}</div>
      ${p.caption?`<div class="post-caption">${esc(p.caption.substring(0,120))}</div>`:''}</div>
      <div style="display:flex;gap:6px;align-items:center;flex-shrink:0">
        <span class="badge badge-yellow">Agendado</span>
        <button class="btn btn-outline btn-sm" onclick="publishNow('${p.id}')">Publicar agora</button>
        <button class="btn btn-ghost btn-sm" onclick="deletePost('${p.id}')" title="Remover">×</button>
      </div>
    </div>`).join('')}</div>`;
}

async function loadPublishedPosts() {
  const r = await api(`/schedule/posts?page_id=${S.client.page_id}&status=published`);
  const c = q('#content-published-list');
  if (!r.ok||!r.posts?.length) { c.innerHTML = '<div class="empty-state"><div class="empty-icon">◎</div><h3>Nenhum post publicado</h3></div>'; return; }
  c.innerHTML = `<div class="posts-list">${r.posts.map(p=>`
    <div class="post-row">
      ${p.image_url?`<img class="post-thumb" src="${p.image_url}" onerror="this.style.display='none'"/>`:'<div class="post-thumb"></div>'}
      <div class="post-info"><div class="post-name">${esc(p.page_name||'Post')}</div>
      <div class="post-meta">Publicado ${fmtDate(p.published_at||p.scheduled_at)}</div>
      ${p.caption?`<div class="post-caption">${esc(p.caption.substring(0,120))}</div>`:''}</div>
      <span class="badge badge-green">Publicado</span>
    </div>`).join('')}</div>`;
}

async function loadDrafts() {
  const r = await api(`/panel/content-plans?page_id=${S.client.page_id}`);
  const c = q('#content-drafts-list');
  const drafts = (r.plans || []).filter(p => p.plan_type === 'single');
  if (!r.ok || !drafts.length) {
    c.innerHTML = '<div class="empty-state"><div class="empty-icon">◌</div><h3>Nenhum rascunho salvo</h3><p>Use “Salvar rascunho” no conteúdo avulso para reaproveitar ideias depois.</p></div>';
    return;
  }
  c.innerHTML = `<div class="posts-list">${drafts.map(p => {
    const post = (p.posts || [])[0] || {};
    return `
      <div class="post-row" style="cursor:pointer" onclick="loadSingleDraft('${p.id}')">
        ${post.image_url ? `<img class="post-thumb" src="${esc(post.image_url)}" onerror="this.style.display='none'"/>` : '<div class="post-thumb"></div>'}
        <div class="post-info">
          <div class="post-name">${esc(p.title || post.title || 'Rascunho')}</div>
          <div class="post-meta">${fmtDate(p.updated_at)} · Conteúdo avulso</div>
          ${post.caption ? `<div class="post-caption">${esc(post.caption.substring(0, 140))}</div>` : ''}
        </div>
        <span class="badge badge-gray">Rascunho</span>
      </div>`;
  }).join('')}</div>`;
}

async function loadSingleDraft(planId) {
  const r = await api(`/panel/content-plans?page_id=${S.client.page_id}&limit=50`);
  const plan = (r.plans || []).find(p => p.id === planId);
  const post = (plan?.posts || [])[0];
  if (!plan || !post) return;
  openSinglePostModal();
  if (q('#sp-theme')) q('#sp-theme').value = post.theme || '';
  if (q('#sp-image-focus')) q('#sp-image-focus').value = post.image_focus || '';
  if (q('#sp-caption')) q('#sp-caption').value = post.caption || '';
  if (q('#sp-title')) q('#sp-title').value = post.title || '';
  if (q('#sp-subtitle')) q('#sp-subtitle').value = post.brief || '';
  if (q('#sp-image-prompt')) q('#sp-image-prompt').value = post.image_prompt || '';
  if (q('#sp-image-url')) q('#sp-image-url').value = post.image_url || '';
  if (q('#sp-preview-box')) {
    q('#sp-preview-box').innerHTML = renderSinglePostPreview({
      imageUrl: post.image_url || '',
      imageError: '',
    });
  }
  goto('content');
}

async function loadContentGallery() {
  const c = q('#content-gallery-list');
  if (!c) return;
  c.innerHTML = '<div class="loading-state"><div class="spinner"></div>Carregando galeria...</div>';
  const r = await api('/panel/gallery');
  if (!r.ok) {
    c.innerHTML = `<div class="alert alert-error">${esc(r.error || 'Erro ao carregar galeria.')}</div>`;
    return;
  }
  const items = r.images || [];
  if (!items.length) {
    c.innerHTML = '<div class="empty-state"><div class="empty-icon">▣</div><h3>Nenhuma imagem encontrada</h3><p>As imagens geradas e enviadas aparecerão aqui.</p></div>';
    return;
  }
  c.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px">${items.map(img => `
    <div class="card" style="padding:10px">
      <img src="${esc(img.public_url || '')}" alt="" style="width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:10px;border:1px solid var(--border)" />
      <div style="font-size:12px;margin-top:8px;color:var(--text-2);word-break:break-word">${esc(img.filename || '')}</div>
      <div class="post-meta">${img.mtime ? fmtDate(img.mtime) : 'gerada'}</div>
    </div>`).join('')}</div>`;
}

async function loadContentPlans() {
  const r = await api(`/panel/content-plans?page_id=${S.client.page_id}`);
  const c = q('#content-plans-list');
  if (!r.ok||!r.plans?.length) { c.innerHTML = '<div class="empty-state"><div class="empty-icon">◆</div><h3>Nenhum plano salvo</h3></div>'; return; }
  await loadClientAIUsage();
  c.innerHTML = `<div class="posts-list">${r.plans.map(p=>`
    <div class="post-row" style="cursor:pointer" onclick="loadPlanIntoAgents('${p.id}')">
      <div class="post-info">
        <div class="post-name">${esc(p.title || p.page_name || 'Plano')}</div>
        <div class="post-meta">${esc(p.plan_type === 'single' ? 'Conteúdo avulso' : (p.month_label || 'Plano mensal'))} · ${(p.posts||[]).length} posts · ${fmtDate(p.updated_at)}</div>
        <div class="post-meta">${planCostSummary(p)}</div>
      </div>
      <span class="badge badge-blue">${(p.posts||[]).length} posts</span>
    </div>`).join('')}</div>`;
}

function planCostSummary(plan) {
  const posts = Array.isArray(plan.posts) ? plan.posts : [];
  let cost = 0;
  let tokens = 0;
  for (const p of posts) {
    const stats = S.aiUsage?.byPost?.[p.id];
    if (!stats) continue;
    cost += Number(stats.cost_usd || 0);
    tokens += Number(stats.tokens || 0);
  }
  if (!cost && !tokens) return 'Sem custo registrado ainda';
  return `${tokens ? `${formatNum(tokens)} tokens` : '0 tokens'}${cost ? ` · US$ ${cost.toFixed(4)}` : ''}`;
}

async function loadPlanIntoAgents(planId) {
  const r = await api(`/panel/content-plans?page_id=${S.client.page_id}&limit=20`);
  if (!r.ok) return;
  const plan = r.plans?.find(p => p.id === planId);
  if (!plan) return;
  S.plan = (plan.posts||[]).map((p,i) => ({ ...p, _idx: i }));
  S.planId = plan.id;
  S.planMeta = {
    mode: plan.plan_type || 'monthly',
    focus: plan.focus || '',
    title: plan.title || '',
    month_label: plan.month_label || '',
  };
  S.selected.clear();
  await loadClientAIUsage();
  goto('content');
}

async function loadStoryScripts() {
  const c = q('#content-story-scripts-list');
  if (!c) return;
  if (!S.plan.length) await loadSavedPlan();
  const stories = planStoryItems();
  if (!stories.length) {
    c.innerHTML = '<div class="empty-state"><div class="empty-icon">◌</div><h3>Nenhum roteiro de story</h3><p>Quando o plano incluir stories, eles aparecerão aqui por dia.</p></div>';
    return;
  }
  c.innerHTML = `<div class="posts-list">${stories.map(({ item }) => `
    <div class="post-row" style="align-items:flex-start">
      <div class="post-info">
        <div class="post-name">${esc(item.suggested_date || 'Sem data')} · ${esc(item.title || 'Roteiro de story')}</div>
        <div class="post-meta">${esc(item.theme || '')}</div>
        <div style="display:flex;flex-direction:column;gap:6px;margin-top:10px">
          ${(Array.isArray(item.story_script) ? item.story_script : []).map((line, i) => `<div style="padding:8px 10px;border:1px solid var(--border);border-radius:12px;background:var(--surface-2);font-size:13px"><strong>Tela ${i+1}:</strong> ${esc(line)}</div>`).join('')}
        </div>
      </div>
    </div>`).join('')}</div>`;
}

function planRenderablePosts() {
  return S.plan.map((item, idx) => ({ item, idx })).filter(({ item }) => item.format !== 'story_script');
}

function planStoryItems() {
  return S.plan.map((item, idx) => ({ item, idx })).filter(({ item }) => item.format === 'story_script');
}

function renderPlanSummary() {
  const el = q('#agents-plan-summary');
  if (!el || !S.plan.length) { if (el) el.innerHTML = ''; return; }
  const counts = S.plan.reduce((acc, item) => {
    const fmt = item.format || 'static';
    acc[fmt] = (acc[fmt] || 0) + 1;
    return acc;
  }, {});
  const totalCost = Number(S.aiUsage?.summary?.total_cost_usd || 0);
  const totalTokens = Number(S.aiUsage?.summary?.total_tokens || 0);
  el.innerHTML = `<div style="display:flex;gap:8px;flex-wrap:wrap">
    <span class="badge badge-blue">${counts.static || 0} posts estáticos</span>
    <span class="badge badge-yellow">${counts.carousel || 0} carrosséis</span>
    <span class="badge badge-gray">${counts.story_script || 0} roteiros de story</span>
    <span class="badge badge-green">${S.plan.length} itens no plano</span>
    <span class="badge badge-blue">${totalCost ? `US$ ${totalCost.toFixed(4)}` : 'Sem custo IA'}</span>
    <span class="badge badge-gray">${totalTokens ? `${formatNum(totalTokens)} tokens` : '0 tokens'}</span>
  </div>`;
}

function renderStartGenerationButton() {
  const btn = q('#btn-start-plan-generation');
  if (!btn) return;
  const pendingPosts = planRenderablePosts().filter(({ item }) => ['pending', 'error'].includes(item.status)).length;
  btn.style.display = pendingPosts ? '' : 'none';
}

/* ── CALENDAR ──────────────────────────────────────────────── */
async function loadCalendar() {
  q('#content-calendar-container').innerHTML = '<div class="loading-state"><div class="spinner"></div>Carregando...</div>';
  const [s, p] = await Promise.all([
    api(`/schedule/posts?page_id=${S.client.page_id}&status=pending`),
    api(`/schedule/posts?page_id=${S.client.page_id}&status=published`),
  ]);
  const posts = [...(s.posts||[]), ...(p.posts||[])];
  renderCalendar(posts);
}

function renderCalendar(posts=[]) {
  const el = q('#content-calendar-container');
  if (!el) return;
  const d = S.calendarDate, y = d.getFullYear(), m = d.getMonth();
  const months = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
  const days = ['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  const byDate = {};
  posts.forEach(p => {
    const ts = p.scheduled_at||p.published_at||0;
    if (!ts) return;
    const key = new Date(ts*1000).toISOString().split('T')[0];
    (byDate[key] = byDate[key]||[]).push(p);
  });
  const firstDay = new Date(y,m,1).getDay();
  const daysInMonth = new Date(y,m+1,0).getDate();
  const today = new Date().toISOString().split('T')[0];
  let cells = '';
  for (let i=0;i<firstDay;i++) cells += '<div class="cal-cell empty"></div>';
  for (let day=1;day<=daysInMonth;day++) {
    const dk = `${y}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const dp = byDate[dk]||[];
    const isToday = dk===today;
    cells += `<div class="cal-cell${isToday?' today':''}" onclick="showDayPosts('${dk}',event)">
      <span class="cal-day">${day}</span>
      ${dp.length?`<div class="cal-dots">${dp.map(p=>`<span class="dot ${p.status==='published'?'dot-green':'dot-yellow'}" title="${esc(p.caption?.substring(0,40)||'')}"></span>`).join('')}</div>`:''}
    </div>`;
  }
  el.innerHTML = `
    <div class="cal-header">
      <button class="btn btn-ghost btn-sm" onclick="calNavMonth(-1)">← Ant</button>
      <span style="font-size:15px;font-weight:600">${months[m]} ${y}</span>
      <button class="btn btn-ghost btn-sm" onclick="calNavMonth(1)">Próx →</button>
    </div>
    <div class="cal-grid">${days.map(n=>`<div class="cal-head">${n}</div>`).join('')}${cells}</div>
    <div class="cal-legend">
      <span><span class="dot dot-green"></span>Publicado</span>
      <span><span class="dot dot-yellow"></span>Agendado</span>
    </div>
    <div id="cal-day-detail"></div>`;
  el._posts = posts;
}

function calNavMonth(dir) {
  S.calendarDate = new Date(S.calendarDate.getFullYear(), S.calendarDate.getMonth()+dir, 1);
  loadCalendar();
}

function showDayPosts(dk) {
  const el = q('#content-calendar-container');
  const posts = (el?._posts||[]).filter(p => {
    const ts = p.scheduled_at||p.published_at||0;
    return new Date(ts*1000).toISOString().split('T')[0] === dk;
  });
  const det = q('#cal-day-detail');
  if (!det) return;
  if (!posts.length) { det.innerHTML = ''; return; }
  det.innerHTML = `<div style="margin-top:16px;border-top:1px solid var(--border);padding-top:16px">
    <div class="card-title">${fmtDateLong(dk)}</div>
    <div class="posts-list" style="margin-top:10px">${posts.map(p=>`
      <div class="post-row">
        ${p.image_url?`<img class="post-thumb" src="${p.image_url}" onerror="this.style.display='none'"/>`:'<div class="post-thumb"></div>'}
        <div class="post-info"><div class="post-name">${esc(p.page_name||'Post')}</div>
        <div class="post-meta">${fmtDate(p.scheduled_at||p.published_at)}</div>
        ${p.caption?`<div class="post-caption">${esc(p.caption.substring(0,100))}</div>`:''}</div>
        <span class="badge ${p.status==='published'?'badge-green':'badge-yellow'}">${p.status==='published'?'Publicado':'Agendado'}</span>
      </div>`).join('')}
    </div></div>`;
}

async function publishNow(postId) {
  if (!confirm('Publicar agora?')) return;
  const r = await post('/schedule/post/publish-now', { post_id: postId });
  if (r.ok) loadScheduledPosts(); else alert('Erro: '+(r.error||''));
}
async function deletePost(postId) {
  if (!confirm('Remover post agendado?')) return;
  const r = await post('/schedule/post/delete', { post_id: postId });
  if (r.ok) loadScheduledPosts();
}

/* ── SETTINGS ──────────────────────────────────────────────── */
async function loadSettings() {
  loadBrandProfile(); loadConnections();
  if (S.user?.role==='admin') { q('#settings-tab-system')?.classList.remove('hidden'); loadSystemConfig(); loadAIUsageSummary(); loadSystemErrorLogs(); }
  else q('#settings-tab-system')?.classList.add('hidden');
}
function switchSettingsTab(tab, el) {
  document.querySelectorAll('#sec-settings .tab-btn').forEach(b=>b.classList.remove('active'));
  if (el) el.classList.add('active');
  document.querySelectorAll('#sec-settings .tab-panel').forEach(p=>p.classList.remove('active'));
  q(`#settings-${tab}`)?.classList.add('active');
}

async function loadBrandProfile() {
  if (!S.client) return;
  const r = await api('/panel/brand-profiles');
  if (!r.ok) return;
  const pid = String(S.client.page_id);
  const p = (r.profiles||{})[pid] || (r.profiles||{})[S.client.page_id] || {};
  S.brandProfile = p;
  const map = { 'brand-name':'brand_name','brand-tagline':'tagline','brand-description':'description','brand-tone':'tone','brand-audience':'target_audience','brand-products':'key_products','brand-offer':'best_offer','brand-visual':'visual_style','brand-font-preference':'font_preference','brand-competitors':'competitors' };
  for (const [id, key] of Object.entries(map)) { const el = q(`#${id}`); if (el) { const v = p[key]; el.value = Array.isArray(v) ? v.join(', ') : (v||''); } }
  // Auto-fill description from Instagram bio when not set
  const descEl = q('#brand-description');
  if (descEl && !descEl.value && p.instagram_biography) descEl.value = p.instagram_biography;
  // Show/hide Instagram-as-logo button based on available picture
  const igLogoBtn = q('#btn-ig-as-logo');
  if (igLogoBtn) igLogoBtn.style.display = p.instagram_profile_picture_url ? '' : 'none';
  if (q('#brand-palette-source')) q('#brand-palette-source').value = p.palette_source || 'logo';
  if (q('#brand-use-reference-style')) q('#brand-use-reference-style').checked = !!p.use_reference_style;
  if (q('#brand-reference-style-prompt')) q('#brand-reference-style-prompt').value = p.reference_style_prompt || '';
  loadBrandColors(p);
  loadBrandPictures(p);
  // Always reset logo previews before loading new company
  [['#brand-logo-preview', p.logo_url], ['#brand-logo-light-preview', p.logo_light_url]].forEach(([sel, url]) => {
    const el = q(sel); if (!el) return;
    if (url) { el.src = url; el.style.display = ''; } else { el.src = ''; el.style.display = 'none'; }
  });
  const rp = q('#brand-reference-preview');
  if (rp) { if (p.reference_image_url) { rp.src = p.reference_image_url; rp.style.display = ''; } else { rp.src = ''; rp.style.display = 'none'; } }
  renderVisualReferences(p.visual_references || []);
}

function loadBrandColors(profile) {
  const raw = Array.isArray(profile.colors) ? profile.colors.join(', ') : (profile.colors||'');
  const colors = raw.split(',').map(c=>c.trim()).filter(Boolean);
  const c = q('#brand-colors-list');
  if (!c) return;
  c.innerHTML = (colors.length ? colors : ['#6366F1']).map((v,i) => buildColorRow(i,v)).join('');
}
function buildColorRow(idx, value) {
  const hex = /^#[0-9A-Fa-f]{3,6}$/.test(value) ? value : '#6366F1';
  return `<div class="color-row" id="color-row-${idx}">
    <input type="color" class="color-picker-input" value="${hex}" oninput="syncColorHex(${idx},this.value)"/>
    <input type="text" class="form-input color-hex-input" value="${value}" placeholder="#RRGGBB ou rgb()" oninput="syncColorPicker(${idx},this.value)" style="flex:1;font-family:monospace"/>
    <button class="btn btn-ghost btn-sm" onclick="removeColor(${idx})">×</button>
  </div>`;
}
function syncColorHex(idx, val) { const el = q(`#color-row-${idx} .color-hex-input`); if (el) el.value = val; }
function syncColorPicker(idx, val) { if (/^#[0-9A-Fa-f]{6}$/.test(val)) { const el = q(`#color-row-${idx} .color-picker-input`); if (el) el.value = val; } }
function addColor() {
  const c = q('#brand-colors-list');
  if (!c) return;
  const idx = c.querySelectorAll('.color-row').length;
  const div = document.createElement('div');
  div.innerHTML = buildColorRow(idx, '#000000');
  c.appendChild(div.firstElementChild);
}
function removeColor(idx) {
  q(`#color-row-${idx}`)?.remove();
  q('#brand-colors-list')?.querySelectorAll('.color-row').forEach((r,i) => r.id = `color-row-${i}`);
}
function collectColors() {
  return Array.from(document.querySelectorAll('#brand-colors-list .color-row')).map(r => r.querySelector('.color-hex-input')?.value||'').filter(Boolean);
}

function loadBrandPictures(p) {
  if (p.instagram_profile_picture_url) { const el = q('#brand-ig-pic'); if (el) { el.src = p.instagram_profile_picture_url; el.style.display = ''; } }
  if (p.facebook_picture_url) { const el = q('#brand-fb-pic'); if (el) { el.src = p.facebook_picture_url; el.style.display = ''; } }
  if (p.instagram_biography && q('#brand-ig-bio')) q('#brand-ig-bio').textContent = p.instagram_biography;
  if (p.instagram_followers_count && q('#brand-ig-followers')) q('#brand-ig-followers').textContent = formatNum(p.instagram_followers_count)+' seguidores';
}

async function syncBrandMeta() {
  setBtnLoading('#btn-sync-meta', true, 'Sincronizando...');
  const r = await post('/panel/brand-profile/sync-meta', { page_id: S.client.page_id });
  setBtnLoading('#btn-sync-meta', false, 'Sincronizar com Meta');
  if (r.ok) {
    const prof = r.profile || {};
    S.brandProfile = prof;
    loadBrandPictures(prof);
    // Auto-fill description from Instagram bio when field is empty
    const descEl = q('#brand-description');
    if (descEl && !descEl.value && prof.instagram_biography) descEl.value = prof.instagram_biography;
    // Auto-extract colors from Instagram profile picture when no colors are set
    if ((!prof.colors || !prof.colors.length) && prof.instagram_profile_picture_url) {
      const pal = await post('/panel/brand-profile/extract-palette', { page_id: S.client.page_id, source: 'instagram_profile' });
      if (pal.ok && pal.palette?.length) { S.brandProfile = { ...S.brandProfile, colors: pal.palette }; loadBrandColors(S.brandProfile); }
    }
    q('#brand-alert').innerHTML = mkAlert('success', 'Dados sincronizados!');
    // Show "use as logo" button if Instagram picture available
    const igLogoBtn = q('#btn-ig-as-logo');
    if (igLogoBtn) igLogoBtn.style.display = prof.instagram_profile_picture_url ? '' : 'none';
  } else {
    q('#brand-alert').innerHTML = mkAlert('error', r.error||'Erro ao sincronizar.');
  }
  setTimeout(()=>{ q('#brand-alert').innerHTML=''; },4000);
}

async function useInstagramAsLogo() {
  setBtnLoading('#btn-ig-as-logo', true, 'Salvando...');
  const r = await post('/panel/brand-profile/use-instagram-logo', { page_id: S.client.page_id });
  setBtnLoading('#btn-ig-as-logo', false, 'Usar como logo');
  if (r.ok) {
    S.brandProfile = { ...(S.brandProfile || {}), ...(r.profile || {}) };
    const lp = q('#brand-logo-preview'); if (lp && r.logo_url) { lp.src = r.logo_url; lp.style.display = ''; }
    if (Array.isArray(r.palette) && r.palette.length) { S.brandProfile.colors = r.palette; loadBrandColors(S.brandProfile); }
    q('#brand-alert').innerHTML = mkAlert('success', 'Logo do Instagram aplicada!');
  } else {
    q('#brand-alert').innerHTML = mkAlert('error', r.error || 'Erro ao aplicar logo.');
  }
  setTimeout(()=>{ q('#brand-alert').innerHTML=''; },3000);
}

async function uploadLogo(variant = 'dark') {
  const inputId = variant === 'light' ? '#brand-logo-light-file' : '#brand-logo-file';
  const previewId = variant === 'light' ? '#brand-logo-light-preview' : '#brand-logo-preview';
  const file = q(inputId)?.files?.[0];
  if (!file) { q('#brand-alert').innerHTML = mkAlert('error', 'Selecione um arquivo primeiro.'); return; }
  const fd = new FormData();
  fd.append('page_id', S.client.page_id);
  fd.append('file', file);
  fd.append('variant', variant);
  const r = await (await fetch('/panel/brand-profile/upload-logo', { method: 'POST', body: fd })).json();
  if (r.ok && r.logo_url) {
    S.brandProfile = { ...(S.brandProfile || {}), ...(r.profile || {}) };
    if (variant === 'dark') {
      S.brandProfile.logo_url = r.logo_url;
      if (Array.isArray(r.palette) && r.palette.length) { S.brandProfile.colors = r.palette; loadBrandColors(S.brandProfile); }
    } else {
      S.brandProfile.logo_light_url = r.logo_url;
    }
    const lp = q(previewId);
    if (lp) { lp.src = r.logo_url; lp.style.display = ''; }
    const label = variant === 'light' ? 'Logo versão clara enviada!' : 'Logo versão escura enviada!';
    const svgHint = file.name.toLowerCase().endsWith('.svg') && variant === 'dark' ? ' Para extrair cores, use PNG ou JPG.' : '';
    q('#brand-alert').innerHTML = mkAlert('success', label + svgHint);
  } else q('#brand-alert').innerHTML = mkAlert('error', r.error || 'Erro ao enviar logo.');
  setTimeout(() => { q('#brand-alert').innerHTML = ''; }, 3000);
}

function normalizeVisualReferences(refs) {
  return (Array.isArray(refs) ? refs : []).map((ref, idx) => {
    if (typeof ref === 'string') return { id: `legacy-${idx}`, url: ref, label: `Referência ${idx + 1}`, kind: 'brand_reference', use_for_style: true };
    return {
      id: ref.id || `ref-${idx}`,
      url: ref.url || '',
      path: ref.path || '',
      filename: ref.filename || '',
      label: ref.label || ref.filename || `Referência ${idx + 1}`,
      kind: ref.kind || 'brand_reference',
      use_for_style: ref.use_for_style !== false,
      created_at: ref.created_at || 0,
    };
  });
}

function renderVisualReferences(refs) {
  const el = q('#brand-visual-references-list');
  if (!el) return;
  const items = normalizeVisualReferences(refs);
  S.brandProfile = { ...(S.brandProfile || {}), visual_references: items };
  if (!items.length) {
    el.innerHTML = '<div class="muted">Nenhuma referência visual cadastrada.</div>';
    return;
  }
  el.innerHTML = items.map((ref, idx) => `
    <div class="card" style="padding:12px">
      ${ref.url ? `<img src="${esc(ref.url)}" alt="${esc(ref.label)}" style="width:100%;max-height:180px;object-fit:contain;border-radius:10px;background:var(--surface-alt,#f7f7f8);border:1px solid var(--border)" />` : ''}
      <div style="margin-top:10px;font-size:14px;font-weight:600">${esc(ref.label)}</div>
      <div class="muted" style="font-size:12px">${esc(ref.kind || 'referência')}</div>
      <label style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:13px">
        <input type="checkbox" ${ref.use_for_style ? 'checked' : ''} onchange="toggleVisualReferenceStyle(${idx}, this.checked)" />
        Usar para guiar o estilo
      </label>
      <button class="btn btn-ghost btn-sm mt-8" onclick="removeVisualReference(${idx})">Remover</button>
    </div>
  `).join('');
}

function toggleVisualReferenceStyle(idx, checked) {
  const refs = normalizeVisualReferences(S.brandProfile?.visual_references || []);
  if (!refs[idx]) return;
  refs[idx].use_for_style = !!checked;
  S.brandProfile.visual_references = refs;
}

function removeVisualReference(idx) {
  const refs = normalizeVisualReferences(S.brandProfile?.visual_references || []);
  refs.splice(idx, 1);
  S.brandProfile.visual_references = refs;
  renderVisualReferences(refs);
}

async function uploadReferenceImage() {
  const file = q('#brand-reference-file').files?.[0];
  if (!file) return;
  setBtnLoading('#btn-upload-reference', true, 'Enviando...');
  const fd = new FormData();
  fd.append('page_id', S.client.page_id);
  fd.append('file', file);
  const r = await (await fetch('/panel/brand-profile/upload-reference', { method: 'POST', body: fd })).json();
  setBtnLoading('#btn-upload-reference', false, 'Enviar arte principal');
  if (r.ok) {
    S.brandProfile = { ...(S.brandProfile || {}), ...(r.profile || {}) };
    if (q('#brand-reference-preview') && r.reference_image_url) {
      q('#brand-reference-preview').src = r.reference_image_url;
      q('#brand-reference-preview').style.display = '';
    }
    if (Array.isArray(r.palette) && r.palette.length) loadBrandColors({ ...(S.brandProfile || {}), colors: r.palette });
    renderVisualReferences(S.brandProfile.visual_references || []);
    q('#brand-alert').innerHTML = mkAlert('success', 'Arte principal enviada!');
  } else q('#brand-alert').innerHTML = mkAlert('error', r.error || 'Erro ao enviar arte principal.');
  setTimeout(()=>{ q('#brand-alert').innerHTML=''; },3000);
}

async function uploadVisualReferences() {
  const files = Array.from(q('#brand-visual-reference-file').files || []);
  if (!files.length) return;
  setBtnLoading('#btn-upload-visual-reference', true, 'Enviando...');
  const fd = new FormData();
  fd.append('page_id', S.client.page_id);
  fd.append('kind', q('#brand-visual-reference-kind')?.value || 'brand_reference');
  files.forEach(file => fd.append('files', file));
  const r = await (await fetch('/panel/brand-profile/upload-visual-reference', { method: 'POST', body: fd })).json();
  setBtnLoading('#btn-upload-visual-reference', false, 'Enviar referências');
  if (r.ok) {
    S.brandProfile = { ...(S.brandProfile || {}), ...(r.profile || {}) };
    renderVisualReferences(S.brandProfile.visual_references || []);
    q('#brand-alert').innerHTML = mkAlert('success', 'Referências enviadas!');
  } else q('#brand-alert').innerHTML = mkAlert('error', r.error || 'Erro ao enviar referências.');
  setTimeout(()=>{ q('#brand-alert').innerHTML=''; },3000);
}

async function extractBrandPalette() {
  const source = q('#brand-palette-source')?.value || 'logo';
  const refs = normalizeVisualReferences(S.brandProfile?.visual_references || []);
  const referenceId = source === 'visual_reference' ? (refs.find(r => r.use_for_style)?.id || refs[0]?.id || '') : '';
  const r = await post('/panel/brand-profile/extract-palette', { page_id: S.client.page_id, source, reference_id: referenceId });
  if (r.ok) {
    S.brandProfile = { ...(S.brandProfile || {}), ...(r.profile || {}), colors: r.palette || [] };
    loadBrandColors(S.brandProfile);
    q('#brand-alert').innerHTML = mkAlert('success', 'Paleta atualizada!');
  } else q('#brand-alert').innerHTML = mkAlert('error', r.error || 'Não foi possível extrair a paleta.');
  setTimeout(()=>{ q('#brand-alert').innerHTML=''; },3000);
}

async function analyzeVisualReferences() {
  const refs = normalizeVisualReferences(S.brandProfile?.visual_references || []);
  S.brandProfile.visual_references = refs;
  const r = await post('/panel/brand-profile/analyze-visual-references', { page_id: S.client.page_id });
  if (r.ok) {
    S.brandProfile = { ...(S.brandProfile || {}), ...(r.profile || {}) };
    if (q('#brand-reference-style-prompt')) q('#brand-reference-style-prompt').value = r.profile?.reference_style_prompt || r.analysis?.style_prompt || '';
    if (q('#brand-use-reference-style')) q('#brand-use-reference-style').checked = true;
    if (Array.isArray(r.profile?.colors)) loadBrandColors(r.profile);
    q('#brand-alert').innerHTML = mkAlert('success', 'Referências analisadas e aplicadas ao estilo!');
  } else q('#brand-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao analisar referências.');
  setTimeout(()=>{ q('#brand-alert').innerHTML=''; },4000);
}

async function saveBrandProfile() {
  const data = {
    page_id: S.client.page_id,
    brand_name: q('#brand-name')?.value||'', tagline: q('#brand-tagline')?.value||'',
    description: q('#brand-description')?.value||'', tone: q('#brand-tone')?.value||'profissional',
    target_audience: q('#brand-audience')?.value||'', key_products: q('#brand-products')?.value||'',
    best_offer: q('#brand-offer')?.value||'', visual_style: q('#brand-visual')?.value||'',
    font_preference: q('#brand-font-preference')?.value || '',
    colors: collectColors(), competitors: q('#brand-competitors')?.value||'',
    palette_source: q('#brand-palette-source')?.value || 'logo',
    use_reference_style: !!q('#brand-use-reference-style')?.checked,
    reference_style_prompt: q('#brand-reference-style-prompt')?.value || '',
    visual_references: normalizeVisualReferences(S.brandProfile?.visual_references || []),
  };
  const r = await post('/panel/brand-profile/save', data);
  q('#brand-alert').innerHTML = r.ok ? mkAlert('success','Perfil salvo!') : mkAlert('error','Erro: '+(r.error||''));
  if (r.ok) S.brandProfile = { ...S.brandProfile, ...data };
  setTimeout(()=>{ q('#brand-alert').innerHTML=''; },3000);
}

async function analyzeBrandAI() {
  setBtnLoading('#btn-brand-ai', true, 'Analisando...');
  const r = await api('/panel/brand-profile/analyze-ai', { method: 'POST', body: JSON.stringify({ page_id: S.client.page_id }), _timeout: 120000 });
  setBtnLoading('#btn-brand-ai', false, 'Analisar com IA');
  if (r.ok) { loadBrandProfile(); q('#brand-alert').innerHTML = mkAlert('success','Análise concluída!'); setTimeout(()=>{ q('#brand-alert').innerHTML=''; },3000); }
  else q('#brand-alert').innerHTML = mkAlert('error', r.detail||r.error||'Erro na análise.');
}

async function loadConnections() {
  const igCard = q('#conn-instagram-card');
  if (igCard && S.client) igCard.innerHTML = `<div class="card-title">Instagram do cliente</div><div class="loading-state"><div class="spinner"></div>Carregando...</div>`;
  const mr = await api('/panel/pages');
  if (mr.ok && mr.pages?.length) {
    const page = mr.pages.find(p=>String(p.id)===String(S.client.page_id));
    q('#conn-meta-status').innerHTML = `<span class="badge badge-green"><span class="dot dot-green"></span>Conectado · ${mr.pages.length} páginas</span><div class="mt-8"><a href="/meta/connect/start" class="btn btn-outline btn-sm">Reconectar / Adicionar contas</a></div>`;
    q('#conn-pages-list').innerHTML = (mr.pages || []).map((p) => {
      const company = S.companies.find(c => String(c.bindings?.meta?.page_id || c.id) === String(p.id));
      return `<div style="padding:10px 0;border-bottom:1px solid var(--border)">
        <div style="font-size:14px;font-weight:500">${esc(p.name || 'Página')}</div>
        <div style="font-size:12px;color:var(--text-muted)">${esc(String(p.id || ''))}${p.instagram_business_account?.username ? ` · @${esc(p.instagram_business_account.username)}` : ''}</div>
        <div style="margin-top:8px">${company ? `<span class="badge badge-green">Cliente cadastrado: ${esc(company.name || company.id)}</span>` : `<button class="btn btn-outline btn-sm" onclick="createCompanyFromPage('${esc(String(p.id || ''))}')">Cadastrar cliente desta página</button>`}</div>
      </div>`;
    }).join('') || (page ? `<div style="font-size:14px;font-weight:500">${esc(page.name)}</div><div style="font-size:12px;color:var(--text-muted)">${page.id}</div>` : 'Página não encontrada.');
  } else {
    q('#conn-meta-status').innerHTML = '<span class="badge badge-red"><span class="dot dot-red"></span>Não conectado</span>';
    q('#conn-pages-list').innerHTML = 'Nenhuma página disponível.<div class="mt-12"><a href="/meta/connect/start" class="btn btn-outline btn-sm">Conectar conta Meta</a></div>';
  }

  // ── Instagram do cliente ──────────────────────────────────────────────────
  if (igCard && S.client) {
    const availableIgs = (mr.pages || [])
      .filter(p => p.instagram_business_account?.id)
      .map(p => ({ id: p.instagram_business_account.id, username: p.instagram_business_account.username || '', pageName: p.name || '', pageId: String(p.id || '') }));
    const currentIgId = S.client.ig_user_id;
    const currentIgUsername = S.client.ig_username;
    const statusBadge = currentIgUsername
      ? `<span class="badge badge-green"><span class="dot dot-green"></span>@${esc(currentIgUsername)}</span>`
      : '<span class="badge badge-gray"><span class="dot dot-gray"></span>Não vinculado</span>';
    let pickerHtml = '';
    if (availableIgs.length > 0) {
      pickerHtml = `<div class="mt-12">
        <div style="font-size:13px;font-weight:500;margin-bottom:6px">Selecionar Instagram vinculado</div>
        <select id="conn-ig-picker" class="form-select">
          <option value="">— selecione —</option>
          ${availableIgs.map(ig => `<option value="${esc(ig.id)}|${esc(ig.username)}|${esc(ig.pageId)}" ${ig.id === currentIgId ? 'selected' : ''}>@${esc(ig.username)} · ${esc(ig.pageName)}</option>`).join('')}
        </select>
        <button class="btn btn-primary btn-sm mt-8" onclick="saveInstagramBinding()">Salvar</button>
      </div>`;
    } else if (!mr.ok || !mr.pages?.length) {
      pickerHtml = `<div style="font-size:13px;color:var(--text-muted);margin-top:8px">Conecte uma conta Meta para selecionar o Instagram.</div>`;
    } else {
      pickerHtml = `<div style="font-size:13px;color:var(--text-muted);margin-top:8px">Nenhuma página conectada possui Instagram Business vinculado.</div>`;
    }
    igCard.innerHTML = `<div class="card-title">Instagram do cliente</div>
      <div>${statusBadge}</div>
      ${pickerHtml}
      <div class="mt-12"><a href="/meta/connect/start" class="btn btn-outline btn-sm">Refazer OAuth Meta</a></div>`;
  } else if (igCard) {
    igCard.innerHTML = `<div class="card-title">Instagram do cliente</div><div style="font-size:13px;color:var(--text-muted)">Selecione um cliente para gerenciar o Instagram.</div><div class="mt-12"><a href="/meta/connect/start" class="btn btn-outline btn-sm">Conectar conta Meta</a></div>`;
  }
  q('#conn-linkedin-status').innerHTML = '<span class="badge badge-gray"><span class="dot dot-gray"></span>Não configurado</span>';
  q('#conn-x-status').innerHTML = '<span class="badge badge-gray"><span class="dot dot-gray"></span>Não configurado</span>';

  // ── Conta de Anúncios vinculada ao cliente ────────────────────────────────
  const adCard = q('#conn-ad-account-card');
  if (adCard && S.client) {
    const currentBoundId = S.client.ad_account_id || '';
    adCard.innerHTML = `
      <div class="card-title">Conta de Anúncios padrão</div>
      <div style="font-size:13px;color:var(--text-muted);margin-bottom:12px">A conta vinculada é pré-selecionada automaticamente na seção Campanhas.</div>
      <div id="conn-ad-status" class="mb-12">
        ${currentBoundId
          ? `<span class="badge badge-green">Vinculada: ${esc(currentBoundId)}</span>`
          : '<span class="badge badge-gray">Não vinculada</span>'}
      </div>
      <div id="conn-ad-picker" style="display:none;margin-bottom:12px"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-outline btn-sm" onclick="openAdAccountPicker()">Selecionar conta</button>
        ${currentBoundId ? `<button class="btn btn-ghost btn-sm" onclick="unbindAdAccount()">Desvincular</button>` : ''}
      </div>`;
    // Tentar exibir o nome da conta vinculada
    if (currentBoundId) {
      const cr = await api(`/panel/campaigns/context?page_id=${encodeURIComponent(S.client.page_id)}`);
      if (cr.ok) {
        const match = (cr.ad_accounts || []).find(a => a.id === currentBoundId);
        if (match) {
          const statusEl = q('#conn-ad-status');
          if (statusEl) statusEl.innerHTML = `<span class="badge badge-green">Vinculada: ${esc(match.name)} <span style="opacity:.7">(${esc(currentBoundId)})</span></span>`;
        }
      }
    }
  }

  await loadCrmConfig();
}

async function saveInstagramBinding() {
  const sel = q('#conn-ig-picker');
  if (!sel || !S.client) return;
  const parts = (sel.value || '').split('|');
  const igUserId = parts[0] || '';
  const igUsername = parts[1] || '';
  const pageId = parts[2] || S.client.page_id;
  if (!igUserId) return;
  const r = await post('/panel/companies/upsert', {
    id: S.client.id,
    name: S.client.name,
    bindings: { meta: { page_id: pageId, instagram: { ig_user_id: igUserId, username: igUsername } } },
  });
  if (r.ok) {
    await loadCompanies();
    const co = S.companies.find(c => c.id === S.client.id);
    if (co) setClient(co);
    await loadConnections();
  }
}

async function loadCrmConfig() {
  const card = q('#conn-crm-card');
  if (!card) return;
  if (!S.client) {
    card.innerHTML = `<div class="card-title">Leads Ads → CRM</div><div style="font-size:13px;color:var(--text-muted)">Selecione um cliente para configurar a integração.</div>`;
    return;
  }
  card.innerHTML = `<div class="card-title">Leads Ads → CRM</div><div class="loading-state"><div class="spinner"></div>Carregando formulários...</div>`;
  const companyId = S.client.id;
  const [cfgR, formsR] = await Promise.all([
    api(`/panel/companies/${encodeURIComponent(companyId)}/crm-config`),
    api(`/panel/companies/${encodeURIComponent(companyId)}/leadgen-forms`),
  ]);
  const crm = cfgR.ok ? (cfgR.crm || {}) : {};
  const forms = formsR.ok ? (formsR.forms || []) : [];
  const lastSync = crm.last_sync_at ? new Date(crm.last_sync_at * 1000).toLocaleString('pt-BR') : null;
  const formsHtml = forms.length > 0
    ? `<div style="font-size:13px;font-weight:500;margin:14px 0 6px">Formulários Lead Ad a monitorar</div>
       <div style="display:flex;flex-direction:column;gap:6px">
         ${forms.map(f => {
           const checked = (crm.form_ids || []).includes(String(f.id)) ? 'checked' : '';
           return `<label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">
             <input type="checkbox" class="crm-form-check" value="${esc(String(f.id))}" ${checked} />
             ${esc(f.name || f.id)} <span class="muted" style="font-size:11px">${esc(String(f.id))}</span>
           </label>`;
         }).join('')}
       </div>`
    : `<div style="font-size:13px;color:var(--text-muted);margin-top:10px">Nenhum formulário Lead Ad encontrado para a página deste cliente.<br><span style="font-size:12px">Crie um formulário de Lead Ad no Gerenciador de Anúncios do Meta.</span></div>`;
  card.innerHTML = `
    <div class="card-title">Leads Ads → CRM</div>
    <div style="font-size:13px;color:var(--text-muted);margin-bottom:12px">Busca leads novos automaticamente a cada 5 min e envia ao CRM sem duplicar.</div>
    <div id="crm-alert" class="mb-12"></div>
    <label style="display:flex;align-items:center;gap:8px;margin-bottom:14px;cursor:pointer">
      <input type="checkbox" id="crm-enabled" ${crm.enabled ? 'checked' : ''} />
      <span style="font-size:13px;font-weight:500">Sincronização automática ativa</span>
    </label>
    <div class="form-group">
      <label class="form-label">URL do Webhook CRM</label>
      <input id="crm-webhook-url" class="form-input" type="url" value="${esc(crm.webhook_url || '')}" placeholder="https://robotzap.com.br/receive_lead_api.php?token=..." />
    </div>
    <div class="grid2" style="margin-top:8px">
      <div class="form-group">
        <label class="form-label">Pipeline ID (opcional)</label>
        <input id="crm-pipeline-id" class="form-input" value="${esc(String(crm.pipeline_id ?? ''))}" placeholder="Ex: 75" />
      </div>
      <div class="form-group">
        <label class="form-label">Stage ID (opcional)</label>
        <input id="crm-stage-id" class="form-input" value="${esc(String(crm.stage_id ?? ''))}" placeholder="Ex: 724" />
      </div>
    </div>
    ${formsHtml}
    ${lastSync ? `<div style="font-size:12px;color:var(--text-muted);margin-top:12px">Última sync: ${esc(lastSync)}${crm.last_sync_result ? ' · ' + esc(crm.last_sync_result) : ''}</div>` : ''}
    <div class="mt-12" style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-primary btn-sm" onclick="saveCrmConfig()">Salvar</button>
      <button class="btn btn-outline btn-sm" id="crm-sync-btn" onclick="triggerCrmSync()">Sincronizar agora</button>
    </div>`;
}

async function saveCrmConfig() {
  if (!S.client) return;
  const formIds = Array.from(document.querySelectorAll('.crm-form-check:checked')).map(el => el.value);
  const pipelineVal = (q('#crm-pipeline-id')?.value || '').trim();
  const stageVal = (q('#crm-stage-id')?.value || '').trim();
  const r = await post(`/panel/companies/${encodeURIComponent(S.client.id)}/crm-config`, {
    enabled: !!q('#crm-enabled')?.checked,
    webhook_url: (q('#crm-webhook-url')?.value || '').trim(),
    pipeline_id: pipelineVal || null,
    stage_id: stageVal || null,
    form_ids: formIds,
  });
  const alertEl = q('#crm-alert');
  if (alertEl) alertEl.innerHTML = r.ok ? mkAlert('success', 'Configuração CRM salva.') : mkAlert('error', r.error || 'Erro ao salvar.');
}

async function triggerCrmSync() {
  if (!S.client) return;
  const btn = q('#crm-sync-btn');
  const alertEl = q('#crm-alert');
  if (btn) { btn.disabled = true; btn.textContent = 'Sincronizando...'; }
  if (alertEl) alertEl.innerHTML = '';
  const r = await post(`/panel/companies/${encodeURIComponent(S.client.id)}/crm-sync`, {});
  if (btn) { btn.disabled = false; btn.textContent = 'Sincronizar agora'; }
  if (alertEl) {
    alertEl.innerHTML = r.ok
      ? mkAlert('success', r.summary || `${r.sent || 0} leads enviados.`)
      : mkAlert('error', r.error || r.reason || 'Erro na sincronização.');
  }
}

async function openAdAccountPicker() {
  const picker = q('#conn-ad-picker');
  if (!picker) return;
  picker.style.display = '';
  picker.innerHTML = '<div class="loading-state" style="padding:8px 0"><div class="spinner"></div>Carregando contas...</div>';
  const r = await api(`/panel/campaigns/context?page_id=${encodeURIComponent(S.client?.page_id || '')}`);
  if (!r.ok || !r.ad_accounts?.length) {
    picker.innerHTML = '<div style="font-size:13px;color:var(--text-muted)">Nenhuma conta disponível. Conecte uma conta Meta primeiro.</div>';
    return;
  }
  picker.innerHTML = `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">Selecione a conta de anúncios desta empresa:</div>` +
    r.ad_accounts.map(a =>
      `<button class="btn btn-outline btn-sm" style="margin:3px" onclick="bindAdAccount('${esc(a.id)}','${esc(a.name || a.id)}')">
        ${esc(a.name || a.id)} <span style="opacity:.6;font-size:11px">(${esc(a.id)})</span>
        ${a._bound ? ' <strong>· vinculada</strong>' : ''}
      </button>`
    ).join('');
}

async function bindAdAccount(adAccountId, name) {
  const r = await post('/panel/companies/upsert', {
    id: S.client.id,
    bindings: { meta: { ad_account_id: adAccountId } },
  });
  if (r.ok) {
    S.client.ad_account_id = adAccountId;
    const co = S.companies.find(c => c.id === S.client.id);
    if (co) {
      co.bindings = co.bindings || {};
      co.bindings.meta = co.bindings.meta || {};
      co.bindings.meta.ad_account_id = adAccountId;
    }
    loadConnections();
  }
}

async function unbindAdAccount() {
  if (!confirm('Desvincular a conta de anúncios desta empresa?')) return;
  await bindAdAccount('', '');
}


function resetAdminUserForm() {
  S.admin.editingEmail = '';
  if (q('#admin-user-email')) q('#admin-user-email').value = '';
  if (q('#admin-user-name')) q('#admin-user-name').value = '';
  if (q('#admin-user-password')) q('#admin-user-password').value = '';
  if (q('#admin-user-role')) q('#admin-user-role').value = 'user';
  if (q('#admin-user-meta-enabled')) q('#admin-user-meta-enabled').checked = true;
  document.querySelectorAll('#admin-user-pages input[type="checkbox"]').forEach(el => { el.checked = false; });
  document.querySelectorAll('#admin-user-ad-accounts input[type="checkbox"]').forEach(el => { el.checked = false; });
}

function editAdminUser(email) {
  const u = (S.admin.users || []).find(x => String(x.email || '').toLowerCase() === String(email || '').toLowerCase());
  if (!u) return;
  S.admin.editingEmail = u.email || '';
  q('#admin-user-email').value = u.email || '';
  q('#admin-user-name').value = u.name || '';
  q('#admin-user-password').value = '';
  q('#admin-user-role').value = u.role || 'user';
  q('#admin-user-meta-enabled').checked = u.meta_connection_enabled !== false;
  const allowed = new Set((u.allowed_page_ids || []).map(String));
  const allowedAdAccounts = new Set((u.allowed_ad_account_ids || []).map(String));
  document.querySelectorAll('#admin-user-pages input[type="checkbox"]').forEach(el => { el.checked = allowed.has(String(el.value)); });
  document.querySelectorAll('#admin-user-ad-accounts input[type="checkbox"]').forEach(el => { el.checked = allowedAdAccounts.has(String(el.value)); });
  q('#admin-user-email').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function deleteAdminUser(email) {
  if (!email || !confirm(`Excluir usuário ${email}?`)) return;
  const r = await post('/panel/users/delete', { email });
  q('#admin-alert').innerHTML = r.ok ? mkAlert('success', 'Usuário removido.') : mkAlert('error', r.error || 'Erro ao remover usuário.');
  if (r.ok) await loadAdminSection();
}

async function saveAdminUser() {
  const allowed_page_ids = Array.from(document.querySelectorAll('#admin-user-pages input[type="checkbox"]:checked')).map(el => String(el.value || ''));
  const allowed_ad_account_ids = Array.from(document.querySelectorAll('#admin-user-ad-accounts input[type="checkbox"]:checked')).map(el => String(el.value || ''));
  const payload = {
    email: q('#admin-user-email')?.value?.trim() || '',
    name: q('#admin-user-name')?.value?.trim() || '',
    password: q('#admin-user-password')?.value || '',
    role: q('#admin-user-role')?.value || 'user',
    meta_connection_enabled: !!q('#admin-user-meta-enabled')?.checked,
    allowed_page_ids,
    allowed_ad_account_ids,
  };
  const r = await post('/panel/users/upsert', payload);
  q('#admin-alert').innerHTML = r.ok ? mkAlert('success', 'Usuário salvo.') : mkAlert('error', r.error || 'Erro ao salvar usuário.');
  if (r.ok) {
    resetAdminUserForm();
    await loadAdminSection();
  }
}

async function createCompanyFromPage(pageId) {
  const page = (S.pages || []).find(p => String(p.id) === String(pageId));
  if (!page) return;
  const payload = {
    id: String(page.id),
    name: page.name || `Página ${page.id}`,
    bindings: {
      meta: {
        page_id: String(page.id),
        instagram: {
          ig_user_id: page.instagram_business_account?.id || '',
          username: page.instagram_business_account?.username || '',
        },
      },
    },
  };
  const r = await post('/panel/companies/upsert', payload);
  const target = q('#admin-alert') || q('#brand-alert') || q('#cfg-alert');
  if (target) target.innerHTML = r.ok ? mkAlert('success', 'Cliente cadastrado a partir da página conectada.') : mkAlert('error', r.error || 'Erro ao cadastrar cliente.');
  if (r.ok) {
    await loadCompanies();
    const co = S.companies.find(c => c.id === String(page.id));
    if (co && confirm(`Cliente "${co.name}" cadastrado.\n\nDeseja vincular uma conta de anúncios agora?`)) {
      setClient(co);
      goto('settings');
      switchSettingsTab('connections', document.querySelector('#sec-settings .tab-btn[onclick*="connections"]'));
      setTimeout(() => openAdAccountPicker(), 400);
      return;
    }
    if (S.section === 'admin') await loadAdminSection();
    if (S.section === 'settings') await loadConnections();
  }
}

async function createCompanyFromPageAndSelect(pageId) {
  const page = (S.pages || []).find(p => String(p.id) === String(pageId));
  if (!page) return;
  const payload = {
    id: String(page.id),
    name: page.name || `Página ${page.id}`,
    bindings: {
      meta: {
        page_id: String(page.id),
        instagram: {
          ig_user_id: page.instagram_business_account?.id || '',
          username: page.instagram_business_account?.username || '',
        },
      },
    },
  };
  const r = await post('/panel/companies/upsert', payload);
  if (!r.ok) { alert(r.error || 'Erro ao cadastrar cliente.'); return; }
  await loadCompanies();
  const co = S.companies.find(c => c.id === String(page.id));
  if (co) { setClient(co); closeModal('modal-client'); }
}

async function loadAdminSection() {
  if (S.user?.role !== 'admin') return;
  const [ur, pr, ar, cr, dr] = await Promise.all([
    api('/panel/users'),
    api('/panel/pages'),
    api('/panel/ad-accounts'),
    api('/panel/companies'),
    api('/panel/company-dashboard'),
  ]);
  S.admin.users = ur.ok ? (ur.users || []) : [];
  S.admin.pages = pr.ok ? (pr.pages || []) : [];
  S.admin.adAccounts = ar.ok ? (ar.ad_accounts || []) : [];
  S.admin.companies = cr.ok ? (cr.companies || {}) : {};
  const companies = Object.values(S.admin.companies || {});
  q('#admin-summary').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px">
      <div><div style="font-size:24px;font-weight:700">${S.admin.users.length}</div><div class="muted">Usuários</div></div>
      <div><div style="font-size:24px;font-weight:700">${S.admin.pages.length}</div><div class="muted">Páginas</div></div>
      <div><div style="font-size:24px;font-weight:700">${companies.length}</div><div class="muted">Clientes</div></div>
    </div>`;
  q('#admin-meta-status').innerHTML = dr?.summary?.meta?.connected
    ? `<span class="badge badge-green"><span class="dot dot-green"></span>Conectado · ${(dr.summary.meta.pages_count || 0)} páginas</span>`
    : '<span class="badge badge-red"><span class="dot dot-red"></span>Não conectado</span>';
  q('#admin-user-pages').innerHTML = S.admin.pages.map((p) => `<label style="display:flex;gap:8px;align-items:flex-start;padding:8px;border:1px solid var(--border);border-radius:10px"><input type="checkbox" value="${esc(String(p.id || ''))}" /><span><strong>${esc(p.name || 'Página')}</strong><br/><span class="muted" style="font-size:12px">${esc(String(p.id || ''))}${p.instagram_business_account?.username ? ` · @${esc(p.instagram_business_account.username)}` : ''}</span></span></label>`).join('') || '<div class="muted">Nenhuma página disponível.</div>';
  q('#admin-user-ad-accounts').innerHTML = S.admin.adAccounts.map((a) => `<label style="display:flex;gap:8px;align-items:flex-start;padding:8px;border:1px solid var(--border);border-radius:10px"><input type="checkbox" value="${esc(String(a.id || ''))}" /><span><strong>${esc(a.name || 'Conta de anúncios')}</strong><br/><span class="muted" style="font-size:12px">${esc(String(a.id || ''))}${a.business?.name ? ` · ${esc(a.business.name)}` : ''}${a._owner_email ? ` · dono: ${esc(a._owner_email)}` : ''}</span></span></label>`).join('') || '<div class="muted">Nenhuma conta de anúncios disponível.</div>';
  q('#admin-users-list').innerHTML = S.admin.users.map((u) => `
    <div style="padding:12px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
      <div>
        <div style="font-size:14px;font-weight:600">${esc(u.name || u.email || '')}</div>
        <div class="muted" style="font-size:12px">${esc(u.email || '')}</div>
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">
          <span class="badge ${u.role === 'admin' ? 'badge-blue' : 'badge-gray'}">${esc(u.role || 'user')}</span>
          <span class="badge badge-gray">${(u.allowed_page_ids || []).length} páginas</span>
          <span class="badge badge-gray">${(u.allowed_ad_account_ids || []).length} contas de anúncios</span>
          ${u.meta_connection_enabled === false ? '<span class="badge badge-red">OAuth Meta desativado</span>' : '<span class="badge badge-green">OAuth Meta ativo</span>'}
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-outline btn-sm" onclick="editAdminUser('${esc(u.email || '')}')">Editar</button>
        ${String(u.email || '').toLowerCase() !== 'luispessoa18@gmail.com' ? `<button class="btn btn-ghost btn-sm" onclick="deleteAdminUser('${esc(u.email || '')}')">Excluir</button>` : ''}
      </div>
    </div>`).join('') || '<div class="muted">Nenhum usuário cadastrado.</div>';
  q('#admin-pages-list').innerHTML = S.admin.pages.map((p) => {
    const company = companies.find(c => String(c.bindings?.meta?.page_id || c.id) === String(p.id));
    return `<div style="padding:12px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
      <div>
        <div style="font-size:14px;font-weight:600">${esc(p.name || 'Página')}</div>
        <div class="muted" style="font-size:12px">${esc(String(p.id || ''))}${p.instagram_business_account?.username ? ` · @${esc(p.instagram_business_account.username)}` : ''}${p._owner_email ? ` · dono: ${esc(p._owner_email)}` : ''}</div>
      </div>
      <div>${company ? `<span class="badge badge-green">${esc(company.name || company.id)}</span>` : `<button class="btn btn-outline btn-sm" onclick="createCompanyFromPage('${esc(String(p.id || ''))}')">Cadastrar cliente</button>`}</div>
    </div>`;
  }).join('') || '<div class="muted">Nenhuma página conectada.</div>';
}

async function loadSystemConfig() {
  ensureImageConfigSelects();
  const r = await api('/meta/debug/config');
  if (r?.public_base_url) q('#cfg-url').value = r.public_base_url;
  if (r?.app_id) q('#cfg-appid').value = r.app_id;
  if (r?.graph_api_version) q('#cfg-apiver').value = r.graph_api_version;
  if (r?.openai_base_url) q('#cfg-openai-base').value = r.openai_base_url;
  if (r?.cloudinary_cloud_name) q('#cfg-cloudinary-cloud').value = r.cloudinary_cloud_name;
  const ai = r?.ai_settings || {};
  const setRoute = (prefix, key) => {
    const route = ai[key] || {};
    if (q(`#${prefix}-provider`)) q(`#${prefix}-provider`).value = route.provider || q(`#${prefix}-provider`).value;
  };
  setRoute('cfg-ai-copy', 'copy_generation');
  setRoute('cfg-ai-prompt', 'prompt_generation');
  setRoute('cfg-ai-plan', 'plan_generation');
  setRoute('cfg-ai-focus', 'focus_suggestion');
  setRoute('cfg-ai-brand', 'brand_analysis');
  setRoute('cfg-ai-campaign', 'campaign_analysis');
  setRoute('cfg-ai-profile', 'profile_analysis');
  setRoute('cfg-ai-icp', 'icp_analysis');
  setRoute('cfg-ai-image', 'image_generation');
  await Promise.all([
    handleProviderChange('cfg-ai-copy-model', q('#cfg-ai-copy-provider')?.value || 'gemini', ai.copy_generation?.model || ''),
    handleProviderChange('cfg-ai-prompt-model', q('#cfg-ai-prompt-provider')?.value || 'gemini', ai.prompt_generation?.model || ''),
    handleProviderChange('cfg-ai-plan-model', q('#cfg-ai-plan-provider')?.value || 'gemini', ai.plan_generation?.model || ''),
    handleProviderChange('cfg-ai-focus-model', q('#cfg-ai-focus-provider')?.value || 'gemini', ai.focus_suggestion?.model || ''),
    handleProviderChange('cfg-ai-brand-model', q('#cfg-ai-brand-provider')?.value || 'gemini', ai.brand_analysis?.model || ''),
    handleProviderChange('cfg-ai-campaign-model', q('#cfg-ai-campaign-provider')?.value || 'gemini', ai.campaign_analysis?.model || ''),
    handleProviderChange('cfg-ai-profile-model', q('#cfg-ai-profile-provider')?.value || 'gemini', ai.profile_analysis?.model || ''),
    handleProviderChange('cfg-ai-icp-model', q('#cfg-ai-icp-provider')?.value || 'gemini', ai.icp_analysis?.model || ''),
    handleProviderChange('cfg-ai-image-model', q('#cfg-ai-image-provider')?.value || 'nano_banana', ai.image_generation?.model || ''),
  ]);
  updateImageSettingsUI(ai.image_generation || {});
  const ur = await api('/panel/users');
  if (ur.ok && ur.users?.length) {
    q('#sys-users-list').innerHTML = ur.users.map(u=>`
      <div style="padding:8px 0;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">
        <div><div style="font-size:13px;font-weight:500">${esc(u.name||u.email)}</div><div style="font-size:12px;color:var(--text-muted)">${esc(u.email)}</div></div>
        <span class="badge ${u.role==='admin'?'badge-blue':'badge-gray'}">${u.role||'user'}</span>
      </div>`).join('');
  }
}

function setModelOptions(selectId, models, selected='') {
  const el = q(`#${selectId}`);
  if (!el) return;
  const current = selected || el.value || '';
  const unique = [...new Set(['', ...(models || [])])];
  el.innerHTML = unique.map(m => `<option value="${esc(m)}">${m ? esc(m) : 'Modelo automático'}</option>`).join('');
  el.value = unique.includes(current) ? current : '';
}

async function loadOpenAIModels(showAlert=true) {
  const r = await api('/panel/ai/models?provider=openai');
  if (!r.ok) {
    if (showAlert) {
      q('#cfg-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao carregar modelos OpenAI.');
      setTimeout(()=>{ q('#cfg-alert').innerHTML=''; },3000);
    }
    return;
  }
  const textModels = r.text_models || [];
  const imageModels = r.image_models || [];
  S.aiModels.openai = { text_models: textModels, image_models: imageModels };
  if (showAlert) {
    q('#cfg-alert').innerHTML = mkAlert('success', 'Modelos OpenAI atualizados.');
    setTimeout(()=>{ q('#cfg-alert').innerHTML=''; },3000);
  }
}

async function loadProviderModels(provider) {
  provider = (provider || '').trim().toLowerCase();
  if (!provider || provider === 'nano_banana') return { text_models: [], image_models: [] };
  if (S.aiModels[provider]) return S.aiModels[provider];
  const r = await api(`/panel/ai/models?provider=${encodeURIComponent(provider)}`);
  if (!r.ok) throw new Error(r.detail || r.error || `Erro ao carregar modelos ${provider}`);
  const payload = { text_models: r.text_models || [], image_models: r.image_models || [] };
  S.aiModels[provider] = payload;
  return payload;
}

async function handleProviderChange(selectId, provider, selected='') {
  const el = q(`#${selectId}`);
  if (!el) return;
  if (provider === 'nano_banana') {
    setModelOptions(selectId, [], '');
    if (selectId === 'cfg-ai-image-model') updateImageSettingsUI();
    return;
  }
  try {
    const payload = await loadProviderModels(provider);
    const models = selectId === 'cfg-ai-image-model' ? (payload.image_models || []) : (payload.text_models || []);
    setModelOptions(selectId, models, selected);
    if (selectId === 'cfg-ai-image-model') updateImageSettingsUI();
  } catch (e) {
    setModelOptions(selectId, [], '');
    if (selectId === 'cfg-ai-image-model') updateImageSettingsUI();
    q('#cfg-alert').innerHTML = mkAlert('error', String(e));
    setTimeout(()=>{ q('#cfg-alert').innerHTML=''; },3000);
  }
}

function updateImageSettingsUI(values = {}) {
  ensureImageConfigSelects();
  const provider = q('#cfg-ai-image-provider')?.value || 'nano_banana';
  const model = q('#cfg-ai-image-model')?.value || '';
  ensureSelectOptions('cfg-ai-image-size', IMAGE_SELECT_OPTIONS.size, values.size || IMAGE_UI_DEFAULTS.size);
  ensureSelectOptions('cfg-ai-image-background', IMAGE_SELECT_OPTIONS.background, values.background || IMAGE_UI_DEFAULTS.background);
  ensureSelectOptions('cfg-ai-image-output-format', IMAGE_SELECT_OPTIONS.output_format, values.output_format || IMAGE_UI_DEFAULTS.output_format);
  ensureSelectOptions('cfg-ai-image-moderation', IMAGE_SELECT_OPTIONS.moderation, values.moderation || IMAGE_UI_DEFAULTS.moderation);
  let qualityOptions = IMAGE_SELECT_OPTIONS.quality_default;
  if (provider === 'openai' && model.startsWith('gpt-image-')) {
    qualityOptions = IMAGE_SELECT_OPTIONS.quality_openai_gpt_image;
  } else if (provider === 'openai' && model === 'dall-e-3') {
    qualityOptions = IMAGE_SELECT_OPTIONS.quality_openai_dalle3;
  }
  ensureSelectOptions('cfg-ai-image-quality', qualityOptions, values.quality || IMAGE_UI_DEFAULTS.quality);
  normalizeImageQualityUI();
}

function normalizeImageQualityUI() {
  const model = q('#cfg-ai-image-model')?.value || '';
  const qualityEl = q('#cfg-ai-image-quality');
  if (!qualityEl) return;
  const raw = (qualityEl.value || '').trim().toLowerCase();
  if (model.startsWith('gpt-image-')) {
    if (!['low','medium','high','auto'].includes(raw)) qualityEl.value = 'auto';
    return;
  }
  if (model === 'dall-e-3') {
    if (!['standard','hd'].includes(raw)) qualityEl.value = 'standard';
    return;
  }
  qualityEl.value = 'standard';
}

async function loadAIUsageSummary() {
  const r = await api('/panel/ai/usage-summary');
  const el = q('#ai-usage-summary');
  if (!el) return;
  if (!r.ok) { el.innerHTML = `<div class="alert alert-error">${esc(r.error||'Erro ao carregar uso de IA.')}</div>`; return; }
  const s = r.summary || {};
  const byProvider = Object.entries(r.by_provider || {});
  const byOperation = Object.entries(r.by_operation || {});
  el.innerHTML = `
    <div class="metrics-grid" style="margin-bottom:16px">
      <div class="metric-card"><div class="metric-label">Custo total</div><div class="metric-value">US$ ${(s.total_cost_usd||0).toFixed(4)}</div></div>
      <div class="metric-card"><div class="metric-label">Tokens</div><div class="metric-value">${formatNum(s.total_tokens||0)}</div></div>
      <div class="metric-card"><div class="metric-label">Chamadas</div><div class="metric-value">${formatNum(s.entries||0)}</div></div>
    </div>
    <div class="grid2 gap-16">
      <div>${byProvider.map(([k,v])=>`<div style="padding:8px 0;border-bottom:1px solid var(--border)"><strong>${esc(k)}</strong><div style="font-size:12px;color:var(--text-muted)">${formatNum(v.count||0)} chamadas · ${formatNum(v.tokens||0)} tokens · US$ ${(v.cost_usd||0).toFixed(4)}</div></div>`).join('') || '<div class="empty-state"><p>Sem uso registrado.</p></div>'}</div>
      <div>${byOperation.map(([k,v])=>`<div style="padding:8px 0;border-bottom:1px solid var(--border)"><strong>${esc(k)}</strong><div style="font-size:12px;color:var(--text-muted)">${formatNum(v.count||0)} chamadas · ${formatNum(v.tokens||0)} tokens · US$ ${(v.cost_usd||0).toFixed(4)}</div></div>`).join('') || '<div class="empty-state"><p>Sem uso registrado.</p></div>'}</div>
    </div>`;
}

async function loadSystemErrorLogs() {
  const container = q('#sys-error-log-list');
  if (container) container.innerHTML = '<div class="loading-state"><div class="spinner"></div>Carregando log...</div>';
  const r = await api('/panel/system-error-logs?limit=200');
  if (!r.ok) {
    if (container) container.innerHTML = `<div class="alert alert-error">${esc(r.error || 'Erro ao carregar log.')}</div>`;
    return;
  }
  if (q('#sys-error-log-path')) q('#sys-error-log-path').textContent = r.log_path || '';
  const items = Array.isArray(r.items) ? r.items : [];
  if (!items.length) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">◌</div><h3>Nenhum erro registrado</h3><p>Os próximos erros de API, Meta e serviços locais aparecerão aqui.</p></div>';
    return;
  }
  container.innerHTML = items.map(item => renderSystemErrorLogItem(item)).join('');
}

function renderSystemErrorLogItem(item) {
  const ts = item.ts ? new Date(item.ts * 1000).toLocaleString('pt-BR') : 'sem data';
  const meta = [
    item.kind || '',
    item.status_code ? `HTTP ${item.status_code}` : '',
    item.method && item.path ? `${item.method} ${item.path}` : '',
    item.url || '',
    item.script ? `script: ${item.script}` : '',
  ].filter(Boolean).join(' · ');
  const detail = [
    item.message || '',
    item.detail || '',
    item.traceback || '',
    item.stderr || '',
    item.stdout || '',
    item.payload ? JSON.stringify(item.payload, null, 2) : '',
  ].filter(Boolean).join('\n\n');
  return `<div class="card" style="margin-top:10px;background:var(--surface-2)">
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
      <div style="font-size:13px;font-weight:700">${esc(item.message || item.kind || 'Erro')}</div>
      <div style="font-size:11px;color:var(--text-muted)">${esc(ts)}</div>
    </div>
    ${meta ? `<div style="font-size:12px;color:var(--text-2);margin-top:6px">${esc(meta)}</div>` : ''}
    ${detail ? `<pre style="margin:10px 0 0;padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:12px;overflow:auto;white-space:pre-wrap;font-size:11px;line-height:1.45">${esc(detail)}</pre>` : ''}
  </div>`;
}

async function clearSystemErrorLogs() {
  if (!confirm('Limpar o arquivo de log de erros?')) return;
  const r = await post('/panel/system-error-logs/clear', {});
  q('#sys-error-log-alert').innerHTML = r.ok ? mkAlert('success', 'Log limpo.') : mkAlert('error', r.error || 'Erro ao limpar log.');
  setTimeout(() => { if (q('#sys-error-log-alert')) q('#sys-error-log-alert').innerHTML = ''; }, 3000);
  if (r.ok) loadSystemErrorLogs();
}

async function saveConfig() {
  const data = {};
  const url = q('#cfg-url')?.value; if (url) data.public_base_url = url;
  const appid = q('#cfg-appid')?.value; if (appid) data.app_id = appid;
  const apiver = q('#cfg-apiver')?.value; if (apiver) data.graph_api_version = apiver;
  const secret = q('#cfg-secret')?.value; if (secret) data.app_secret = secret;
  const gemini = q('#cfg-gemini')?.value; if (gemini) data.gemini_api_key = gemini;
  const openai = q('#cfg-openai')?.value; if (openai) data.openai_api_key = openai;
  const openaiBase = q('#cfg-openai-base')?.value; if (openaiBase) data.openai_base_url = openaiBase;
  const anthropic = q('#cfg-anthropic')?.value; if (anthropic) data.anthropic_api_key = anthropic;
  const cloudinaryCloud = q('#cfg-cloudinary-cloud')?.value; if (cloudinaryCloud) data.cloudinary_cloud_name = cloudinaryCloud;
  const cloudinaryKey = q('#cfg-cloudinary-key')?.value; if (cloudinaryKey) data.cloudinary_api_key = cloudinaryKey;
  const cloudinarySecret = q('#cfg-cloudinary-secret')?.value; if (cloudinarySecret) data.cloudinary_api_secret = cloudinarySecret;
  data.ai_settings = {
    copy_generation: { provider: q('#cfg-ai-copy-provider')?.value || 'gemini', model: q('#cfg-ai-copy-model')?.value || '' },
    prompt_generation: { provider: q('#cfg-ai-prompt-provider')?.value || 'gemini', model: q('#cfg-ai-prompt-model')?.value || '' },
    plan_generation: { provider: q('#cfg-ai-plan-provider')?.value || 'gemini', model: q('#cfg-ai-plan-model')?.value || '' },
    focus_suggestion: { provider: q('#cfg-ai-focus-provider')?.value || 'gemini', model: q('#cfg-ai-focus-model')?.value || '' },
    brand_analysis: { provider: q('#cfg-ai-brand-provider')?.value || 'gemini', model: q('#cfg-ai-brand-model')?.value || '' },
    campaign_analysis: { provider: q('#cfg-ai-campaign-provider')?.value || 'gemini', model: q('#cfg-ai-campaign-model')?.value || '' },
    profile_analysis: { provider: q('#cfg-ai-profile-provider')?.value || 'gemini', model: q('#cfg-ai-profile-model')?.value || '' },
    icp_analysis: { provider: q('#cfg-ai-icp-provider')?.value || 'gemini', model: q('#cfg-ai-icp-model')?.value || '' },
    image_generation: {
      provider: q('#cfg-ai-image-provider')?.value || 'nano_banana',
      model: q('#cfg-ai-image-model')?.value || '',
      size: q('#cfg-ai-image-size')?.value || '1024x1024',
      quality: q('#cfg-ai-image-quality')?.value || 'standard',
      background: q('#cfg-ai-image-background')?.value || 'auto',
      output_format: q('#cfg-ai-image-output-format')?.value || 'png',
      moderation: q('#cfg-ai-image-moderation')?.value || 'auto',
    },
  };
  const r = await post('/config/save-json', data);
  q('#cfg-alert').innerHTML = r.ok ? mkAlert('success','Salvo!') : mkAlert('error',r.error||'Erro.');
  setTimeout(()=>{ q('#cfg-alert').innerHTML=''; },3000);
  if (r.ok) loadAIUsageSummary();
}

async function loadICP(refresh=false) {
  if (!S.client) return;
  const el = q('#icp-content');
  if (el) el.innerHTML = '<div class="loading-state"><div class="spinner"></div>Carregando ICP salvo...</div>';
  const r = await api(`/panel/icp?page_id=${S.client.page_id}&refresh=false`);
  if (!r.ok) {
    q('#icp-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao carregar ICP.');
    if (el) el.innerHTML = '<div class="empty-state"><p>Não foi possível carregar o ICP. Tente de novo.</p></div>';
    return;
  }
  const profile = (r.context || {}).brand_profile || {};
  if (q('#icp-onboarding-text')) q('#icp-onboarding-text').value = profile.icp_onboarding_text || '';
  if (q('#icp-compare-notes')) q('#icp-compare-notes').value = profile.icp_compare_notes || '';
  if (q('#icp-adjustment-notes')) q('#icp-adjustment-notes').value = profile.icp_adjustment_notes || '';
  renderICPAnalysis(r.analysis || {}, r.context || {});
}

async function saveICPContext() {
  if (!S.client) return;
  setBtnLoading('#btn-icp-save-context', true, 'Salvando...');
  const payload = {
    page_id: S.client.page_id,
    icp_onboarding_text: q('#icp-onboarding-text')?.value?.trim() || '',
    icp_compare_notes: q('#icp-compare-notes')?.value?.trim() || '',
    icp_adjustment_notes: q('#icp-adjustment-notes')?.value?.trim() || '',
  };
  const r = await post('/panel/brand-profile/save', payload);
  setBtnLoading('#btn-icp-save-context', false, 'Salvar contexto');
  q('#icp-alert').innerHTML = r.ok ? mkAlert('success', 'Contexto salvo.') : mkAlert('error', r.detail || r.error || 'Erro ao salvar contexto.');
  if (r.ok) S.brandProfile = { ...S.brandProfile, ...payload };
  setTimeout(() => { if (q('#icp-alert')) q('#icp-alert').innerHTML = ''; }, 4000);
}

async function generateICP(mode='generate') {
  if (!S.client) return;
  const btnSel = mode === 'adjust' ? '#btn-icp-adjust' : '#btn-icp-refresh';
  setBtnLoading(btnSel, true, mode === 'adjust' ? 'Ajustando...' : 'Gerando...');
  q('#icp-alert').innerHTML = '';
  q('#icp-content').innerHTML = `<div class="loading-state"><div class="spinner"></div>${mode === 'adjust' ? 'Ajustando ICP com base nas suas sugestões...' : 'Gerando ICP com base no contexto salvo...'}</div>`;
  const r = await api('/panel/icp/generate', { method: 'POST', body: JSON.stringify({
    page_id: S.client.page_id,
    mode,
    onboarding_text: q('#icp-onboarding-text')?.value?.trim() || '',
    compare_notes: q('#icp-compare-notes')?.value?.trim() || '',
    adjustment_notes: q('#icp-adjustment-notes')?.value?.trim() || '',
  }), _timeout: 120000 });
  setBtnLoading(btnSel, false, mode === 'adjust' ? 'Ajustar ICP' : 'Gerar ICP');
  if (!r.ok) {
    q('#icp-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Erro ao gerar ICP.');
    await loadICP();
    return;
  }
  q('#icp-alert').innerHTML = mkAlert('success', mode === 'adjust' ? 'ICP ajustado e salvo.' : 'ICP gerado e salvo.');
  renderICPAnalysis(r.analysis || {}, r.context || {});
  setTimeout(() => { if (q('#icp-alert')) q('#icp-alert').innerHTML = ''; }, 4000);
}

function icpAnalysisHasContent(a) {
  if (!a || typeof a !== 'object') return false;
  return Object.keys(a).some((k) => !String(k).startsWith('_'));
}

function renderICPAnalysis(a = {}, context = {}) {
  const el = q('#icp-content');
  if (!el) return;
  if (!icpAnalysisHasContent(a)) {
    const history = Array.isArray(context.icp_analysis_history) ? context.icp_analysis_history.slice().reverse() : [];
    const last = history[0];
    const lastLine = last
      ? `<p class="post-meta" style="margin-top:12px">Última geração registada: <strong>${esc(fmtDate(last.ts))}</strong> (${last.mode === 'adjust' ? 'ajuste' : 'geração'}). Resumo no histórico abaixo.</p>`
      : '';
    el.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">◌</div>
        <h3>Nenhum ICP nesta página</h3>
        <p>O ICP fica guardado <strong>por página</strong> Meta (outra empresa ou outra página = outro conjunto de dados).</p>
        <p>O contexto pode ficar salvo sem disparar IA. Quando quiser, clique em Gerar ICP.</p>
        ${lastLine}
      </div>
      ${history.length ? `<div class="card mt-16"><div class="card-title">Histórico de análises salvas</div><div style="font-size:13px;color:var(--text-2)">${history.map(item=>`<div style="padding:8px 0;border-bottom:1px solid var(--border)"><strong>${esc(item.mode === 'adjust' ? 'Ajuste' : 'Geração')}</strong> · ${esc(fmtDate(item.ts))}<br/>${esc(item.analysis_text || item.overview || 'Sem resumo')}</div>`).join('')}</div></div>` : ''}`;
    return;
  }
  const d = a.demographics || {};
  const p = a.persona || {};
  const e = a.empathy_map || {};
  const alignment = a.owner_alignment || {};
  const history = Array.isArray(context.icp_analysis_history) ? context.icp_analysis_history.slice().reverse() : [];
  el.innerHTML = `
    ${a.analysis_text ? `<div class="card mb-16"><div class="card-title">Leitura em texto</div><p style="white-space:pre-line">${esc(a.analysis_text)}</p></div>` : ''}
    <div class="grid2 gap-16">
      <div class="card"><div class="card-title">Visão geral</div><p>${esc(a.overview || 'Sem resumo gerado.')}</p></div>
      <div class="card"><div class="card-title">Demografia inferida</div><div style="font-size:13px;color:var(--text-2)">Faixa etária: ${esc(d.age_range||'—')}<br/>Gênero: ${esc(d.gender_mix||'—')}<br/>Renda: ${esc(d.income_band||'—')}<br/>Regiões: ${esc((d.regions||[]).join(', ')||'—')}</div></div>
      <div class="card"><div class="card-title">Persona</div><div style="font-size:13px;color:var(--text-2)"><strong>${esc(p.name||'Persona principal')}</strong><br/>${esc(p.summary||'')}</div><div class="post-meta" style="margin-top:8px">Objetivos: ${esc((p.goals||[]).join(', ')||'—')}</div><div class="post-meta">Dores: ${esc((p.pain_points||[]).join(', ')||'—')}</div></div>
      <div class="card"><div class="card-title">Mapa de empatia</div><div style="font-size:13px;color:var(--text-2)">Pensa: ${esc((e.thinks||[]).join(', ')||'—')}<br/>Sente: ${esc((e.feels||[]).join(', ')||'—')}<br/>Vê: ${esc((e.sees||[]).join(', ')||'—')}<br/>Ouve: ${esc((e.hears||[]).join(', ')||'—')}<br/>Fala/Faz: ${esc((e.says_and_does||[]).join(', ')||'—')}</div></div>
    </div>
    <div class="grid2 gap-16 mt-16">
      <div class="card"><div class="card-title">Sua visão x dados</div><div style="font-size:13px;color:var(--text-2)">${(alignment.matches||[]).map(x=>`<div style="padding:6px 0;border-bottom:1px solid var(--border)">Confirma: ${esc(x)}</div>`).join('') || 'Sem pontos confirmados.'}</div></div>
      <div class="card"><div class="card-title">Diferenças e perguntas</div><div style="font-size:13px;color:var(--text-2)">${[...(alignment.differences||[]), ...(alignment.questions||[])].map(x=>`<div style="padding:6px 0;border-bottom:1px solid var(--border)">${esc(x)}</div>`).join('') || 'Sem divergências registradas.'}</div></div>
    </div>
    <div class="card mt-16"><div class="card-title">Gaps competitivos</div><div style="font-size:13px;color:var(--text-2)">${(a.competitor_gaps||[]).map(x=>`<div style="padding:6px 0;border-bottom:1px solid var(--border)">${esc(x)}</div>`).join('') || 'Sem gaps registrados.'}</div></div>
    <div class="card mt-16"><div class="card-title">Oportunidades e recomendações</div><div style="font-size:13px;color:var(--text-2)">${[...(a.content_opportunities||[]), ...(a.recommendations||[])].map(x=>`<div style="padding:6px 0;border-bottom:1px solid var(--border)">${esc(x)}</div>`).join('') || 'Sem recomendações.'}</div></div>
    <div class="card mt-16"><div class="card-title">Histórico de análises salvas</div><div style="font-size:13px;color:var(--text-2)">${history.map(item=>`<div style="padding:8px 0;border-bottom:1px solid var(--border)"><strong>${esc(item.mode === 'adjust' ? 'Ajuste' : 'Geração')}</strong> · ${esc(fmtDate(item.ts))}<br/>${esc(item.analysis_text || item.overview || 'Sem resumo')}</div>`).join('') || 'Nenhuma análise anterior salva.'}</div></div>
  `;
}

/* ── ANALYSIS SECTION ──────────────────────────────────────── */
function getInstaScrapeUsername() {
  const bp = S.brandProfile || {};
  const raw = (bp.instagram_handle || '').toString().trim().replace(/^@/, '');
  const fromBrand = raw.split(/[/?\s]/)[0] || '';
  if (fromBrand) return fromBrand;
  return String(S.client.ig_username || '').trim().replace(/^@/, '');
}

function igAnalysisHasMeaningfulContent(a) {
  if (!a || typeof a !== 'object') return false;
  if (a.header && (a.header.subtitle || (a.header.stats && Object.keys(a.header.stats).length))) return true;
  if (a.diagnosis && (a.diagnosis.positioning_verdict || a.diagnosis.central_problem)) return true;
  if (Array.isArray(a.quick_wins) && a.quick_wins.length) return true;
  if (a.strategy && a.strategy.new_positioning) return true;
  return Object.keys(a).filter((k) => !k.startsWith('_')).length > 0;
}

function renderRecentPostsGrid(posts) {
  const list = Array.isArray(posts) ? posts.filter((p) => p && p.image_url) : [];
  if (!list.length) return '';
  return `<div class="card" style="margin-top:16px">
    <div class="card-title">Últimos posts</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:8px">
      ${list.slice(0, 12).map((p) => {
        const u = p.permalink || p.image_url || '#';
        return `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer" style="display:block;aspect-ratio:1;border-radius:10px;overflow:hidden;border:1px solid var(--border)">
          <img src="${esc(p.image_url)}" alt="" style="width:100%;height:100%;object-fit:cover" loading="lazy" onerror="this.parentElement.style.display='none'"/>
        </a>`;
      }).join('')}
    </div>
  </div>`;
}

function renderOwnAnalysisTeaser(own) {
  const a = own.analysis || {};
  const profile = own.profile || {};
  if (!igAnalysisHasMeaningfulContent(a)) {
    return `${renderRecentPostsGrid(profile.recent_posts)}
    <div class="alert alert-info" style="margin-top:14px">Sem análise de IA no histórico. O botão <strong>«Análise com IA»</strong> precisa de chave de API configurada; «Atualizar dados» só traz números e a grelha de posts, sem o relatório.</div>`;
  }
  const h = a.header || {};
  const d = a.diagnosis || {};
  const qw = Array.isArray(a.quick_wins) ? a.quick_wins.slice(0, 5) : [];
  return `${renderRecentPostsGrid(profile.recent_posts)}
  <div class="card" style="margin-top:16px">
    <div class="card-title">Leitura da IA (resumo)</div>
    ${h.subtitle || d.current_positioning ? `<p style="font-size:14px;line-height:1.55;margin:0 0 10px">${esc(h.subtitle || d.current_positioning || '')}</p>` : ''}
    ${d.positioning_verdict ? `<p style="font-size:15px;font-weight:600;margin:0 0 8px">✓ O que funciona / veredicto</p><p style="font-size:14px;margin:0 0 10px">${esc(d.positioning_verdict)}</p>` : ''}
    ${d.central_problem ? `<p style="font-size:14px;font-weight:600;margin:0 0 4px">⚠ Atenção</p><p style="font-size:13px;color:var(--text-2);line-height:1.55;margin:0 0 10px">${esc(d.central_problem)}</p>` : ''}
    ${qw.length ? `<div><div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:6px">Melhorias rápidas</div><ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.5">${qw.map((x) => `<li><strong>${esc((x && x.title) || '')}</strong> — ${esc((x && x.description) || '')}</li>`).join('')}</ul></div>` : ''}
  </div>
  <div style="margin-top:12px">
    <button class="btn btn-outline btn-sm" type="button" onclick="showAnalysisModal(${JSON.stringify(own.username)})">Abrir análise completa →</button>
  </div>`;
}

async function loadAnalysis() {
  if (!S.client) return;
  q('#analysis-sub').textContent = `Instagram · ${S.client.name}`;
  const br = await api('/panel/brand-profiles');
  if (br && br.ok) {
    S.brandProfile = (br.profiles || {})[S.client.page_id] || {};
  }
  await loadInstaSessions();
  await loadAnalysisOwn();
  await loadAnalysisCompetitors();
}

async function loadInstaSessions() {
  const r = await api('/panel/insta/sessions');
  S._instaDefaultSession = String(r.default_session || '').trim();
  S._instaLoginSession = String(r.login_session || '').trim() || S._instaDefaultSession;
  S._instaSessionCount = Array.isArray(r.sessions) ? r.sessions.length : 0;
  const sel = q('#analysis-session-select');
  if (!sel) return;
  const par = sel.parentElement;
  let hint = q('#analysis-login-hint');
  if (!hint && par) {
    hint = document.createElement('p');
    hint.id = 'analysis-login-hint';
    hint.setAttribute('class', 'muted');
    hint.style.cssText = 'font-size:12px;margin:0 0 10px;line-height:1.45';
    par.insertBefore(hint, sel);
  }
  const alvo = getInstaScrapeUsername() || (String(S.client?.ig_username || '').replace(/^@/, '') || '—');
  if (hint) {
    if (S._instaLoginSession) {
      hint.textContent = `Login do browser (cookies): @${S._instaLoginSession} — isso NÃO é o perfil a analisar. Puxamos dados de @${alvo} (Brand “Handle Instagram” ou, se vazio, o IG vinculado na Meta a esta página).`;
    } else {
      hint.textContent = 'Sem ficheiro em instascrapper/sessions/. Nessa máquina (onde corre o painel) rode: python3 instascrapper/main.py login homeunity <senha> — a conta de login costuma ser homeunity; o perfil lido no botão "Atualizar" é @' + alvo + ' (Ribus etc.), não a conta de login.';
    }
  }
  sel.style.display = 'none';
  sel.innerHTML = '';
}

async function loadAnalysisOwn() {
  const r = await api(`/panel/insta/competitors?page_id=${S.client.page_id}`);
  if (!r.ok) { renderOwnProfileEmpty(); return; }
  if (r.last_insta_analyze_diagnostics) S._instaRunDiagnostics = r.last_insta_analyze_diagnostics;
  S._competitorsCache = r.competitors || [];
  const own = (r.competitors || []).find(c => c.is_own);
  if (!own) { renderOwnProfileEmpty(); return; }
  renderOwnProfileCard(own);
  // Load competitors too (they appear in the same response)
  renderCompetitorsList(r.competitors || []);
  renderComparisonChart(r.competitors || []);
}

function renderInstaRunDiagnosticsCard(d) {
  if (!d || typeof d !== 'object') return '';
  const failed = d.failed === true;
  const okJson = d.analysis_json_generated === true || (d.analysis_key_count > 0);
  if (!failed && okJson) return '';
  const border = failed ? 'var(--danger)' : (okJson ? 'var(--success)' : 'var(--warning)');
  const categoryLabel = ({
    success: 'Concluído',
    profile_fetch_failed: 'Falha ao ler perfil',
    scrape_failed: 'Falha no scrape',
    ai_key_missing: 'Chave ausente',
    ai_provider_failed: 'Falha no provider IA',
    ai_json_parse_failed: 'Falha no parse do JSON',
    analysis_empty: 'Análise vazia',
  })[d.failure_category || ''] || 'Diagnóstico';
  const rows = failed
    ? [
        ['Erro', d.error || '—'],
        ['Detalhe', d.detail || '—'],
        ['Sessões tentadas', Array.isArray(d.tried_sessions) ? d.tried_sessions.join(', ') : '—'],
      ]
    : [
        ['Origem', d.cached ? 'Cache em disco' : 'Corrida nova'],
        ['Sessão usada', d.session_used || '—'],
        ['Perfil (JSON)', d.profile_fetched ? 'OK' : `Erro: ${d.profile_error || '—'}`],
        ['ZIP do scrape', d.zip_ok === true ? 'gerado' : d.zip_ok === false ? 'falhou ou vazio' : '—'],
        ['Chave IA no processo', d.ai_key_configured ? 'sim' : 'não'],
        ['Bloco IA executado', d.ai_ran ? 'sim' : 'não'],
        ['Relatório JSON (análise)', okJson ? `sim (${d.analysis_key_count || 0} chaves)` : 'não'],
        ['Motivo se vazio', d.ai_skip_reason || '—'],
        ['Etapa', d.stage || '—'],
        ['Categoria', categoryLabel],
        ['Modelo', [d.provider, d.model].filter(Boolean).join(' / ') || '—'],
      ];
  const tail = (d.script_stderr_tail || '').trim();
  return `<div class="card" style="margin-bottom:14px;border-left:4px solid ${border}">
    <div class="card-title">${failed ? 'Falha na execução' : 'Última execução «Analisar com IA»'} · ${esc(categoryLabel)}</div>
    <p class="muted" style="font-size:12px;margin:0 0 10px;line-height:1.45">${esc(d.user_hint || '')}</p>
    <table style="width:100%;font-size:12px;border-collapse:collapse">
      ${rows.map(([k, v]) => `<tr><td style="padding:4px 8px 4px 0;color:var(--text-muted);vertical-align:top;white-space:nowrap">${esc(k)}</td><td style="padding:4px 0">${esc(String(v))}</td></tr>`).join('')}
    </table>
    ${tail ? `<details style="margin-top:10px"><summary style="cursor:pointer;font-size:12px;color:var(--text-muted)">Stderr do script (fim)</summary><pre style="font-size:11px;overflow:auto;max-height:160px;background:var(--surface-2);padding:8px;border-radius:8px;margin-top:6px;white-space:pre-wrap">${esc(tail)}</pre></details>` : ''}
    ${failed || !okJson ? `<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;color:var(--text-muted)">JSON técnico completo</summary><pre style="font-size:10px;overflow:auto;max-height:200px;margin-top:6px;background:var(--surface-2);padding:8px;border-radius:8px">${esc(JSON.stringify(d, null, 2))}</pre></details>` : ''}
  </div>`;
}

function renderOwnProfileEmpty() {
  const def = S._instaDefaultSession;
  const sub = def
    ? `<p class="muted" style="font-size:12px;margin-top:6px">Leitura de dados usa a sessão <strong>@${esc(def)}</strong> do servidor. O alvo analisado é o Instagram vinculado a esta página.</p>`
    : '<p>Clique em "Atualizar dados" para buscar seguidores, bio e pré-visualização de posts. Confirme <code>INSTASCRAPPER_DEFAULT_SESSION</code> no instascrapper se quiser uma conta fixa de leitura.</p>';
  q('#analysis-own-content').innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">◑</div>
      <h3>Perfil não analisado ainda</h3>
      ${sub}
    </div>`;
}

function renderOwnProfileCard(own) {
  const profile = own.profile || {};
  const analysis = own.analysis || {};
  const header = (analysis.header || {});
  const stats = header.stats || {};
  const profPic = profile.avatar_url || profile.profile_pic_url || profile.profile_picture_url || '';
  const bio = profile.bio || profile.biography || '';
  const followers = own.followers || stats.followers || profile.followers || 0;
  const following = own.following || profile.following || 0;
  const posts = own.posts || stats.posts || profile.posts || 0;
  const engRate = stats.engagement_rate || '';
  const delta = own.delta || 0;
  const deltaHtml = delta !== 0
    ? `<span class="metric-delta ${delta>0?'up':'down'}">${delta>0?'+':''}${formatNum(delta)} desde ontem</span>`
    : `<span class="metric-delta neutral">Sem dados anteriores</span>`;

  q('#analysis-own-content').innerHTML = `
    ${renderInstaRunDiagnosticsCard(S._instaRunDiagnostics)}
    <div style="display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap">
      <div style="display:flex;gap:14px;align-items:flex-start;flex:1;min-width:260px">
        ${profPic ? `<img src="${profPic}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid var(--border)" onerror="this.style.display='none'"/>` : '<div style="width:64px;height:64px;border-radius:50%;background:var(--primary-light);flex-shrink:0"></div>'}
        <div style="flex:1;min-width:0">
          <div style="font-size:16px;font-weight:700">@${esc(own.username)}</div>
          ${bio ? `<div style="font-size:12px;color:var(--text-2);margin-top:4px;line-height:1.5;max-width:320px">${esc(bio.substring(0,150))}</div>` : ''}
          ${own.last_scraped ? `<div style="font-size:11px;color:var(--text-muted);margin-top:6px">Última análise: ${esc(own.last_scraped)}</div>` : ''}
        </div>
      </div>
      <div style="display:flex;gap:20px;flex-wrap:wrap">
        <div style="text-align:center">
          <div style="font-size:22px;font-weight:700">${formatNum(followers)}</div>
          <div style="font-size:12px;color:var(--text-muted)">Seguidores</div>
          ${deltaHtml}
        </div>
        <div style="text-align:center">
          <div style="font-size:22px;font-weight:700">${formatNum(posts)}</div>
          <div style="font-size:12px;color:var(--text-muted)">Posts</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:22px;font-weight:700">${formatNum(following)}</div>
          <div style="font-size:12px;color:var(--text-muted)">Seguindo</div>
        </div>
        ${engRate ? `<div style="text-align:center"><div style="font-size:22px;font-weight:700">${esc(engRate)}</div><div style="font-size:12px;color:var(--text-muted)">Engajamento</div></div>` : ''}
      </div>
    </div>
    ${renderOwnAnalysisTeaser(own)}`;
}

async function loadAnalysisCompetitors() {
  const r = await api(`/panel/insta/competitors?page_id=${S.client.page_id}`);
  if (!r.ok) return;
  S._competitorsCache = r.competitors || [];
  const comps = (r.competitors || []).filter(c => !c.is_own);
  renderCompetitorsList(comps);
  renderComparisonChart(r.competitors || []);
}

function renderCompetitorsList(allComps) {
  const comps = allComps.filter(c => !c.is_own);
  const container = q('#analysis-competitors-list');
  if (!container) return;
  if (!comps.length) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">◈</div><h3>Nenhum concorrente mapeado</h3><p>Adicione perfis para comparar.</p></div>`;
    return;
  }
  container.innerHTML = `<div class="posts-list">${comps.map(c => {
    const profile = c.profile || {};
    const profPic = profile.avatar_url || profile.profile_pic_url || profile.profile_picture_url || '';
    const hasAnalysis = Object.keys(c.analysis || {}).length > 0;
    const delta = c.delta || 0;
    const deltaHtml = delta !== 0
      ? `<span style="font-size:12px;font-weight:500;color:${delta>0?'var(--success)':'var(--danger)'}">${delta>0?'+':''}${formatNum(delta)}</span>`
      : '';
    return `<div class="post-row">
      ${profPic ? `<img class="post-thumb" src="${profPic}" style="border-radius:50%" onerror="this.style.display='none'"/>` : '<div class="post-thumb" style="border-radius:50%;background:var(--surface-alt)"></div>'}
      <div class="post-info">
        <div class="post-name">@${esc(c.username)}${c.label ? ` · ${esc(c.label)}` : ''}</div>
        <div class="post-meta">${formatNum(c.followers)} seguidores ${deltaHtml} · ${c.posts} posts${c.last_scraped ? ` · Analisado ${esc(c.last_scraped)}` : ''}</div>
      </div>
      <div style="display:flex;gap:6px;align-items:center;flex-shrink:0;flex-wrap:wrap;justify-content:flex-end">
        ${hasAnalysis ? `<button class="btn btn-outline btn-sm" onclick="showAnalysisModal('${esc(c.username)}')">Ver análise</button>` : ''}
        <button class="btn btn-primary btn-sm" type="button" onclick="compareCompetitorToOwn(${JSON.stringify(c.username)})">Vs. o meu perfil</button>
        <button class="btn btn-ghost btn-sm" id="btn-analyze-comp-${esc(c.username)}" onclick="analyzeCompetitor(${JSON.stringify(c.username)})">Analisar</button>
        <button class="btn btn-ghost btn-sm" onclick="removeCompetitor(${JSON.stringify(c.username)})" title="Remover">×</button>
      </div>
    </div>`;
  }).join('')}</div>`;
}

function renderComparisonChart(allComps) {
  const card = q('#analysis-comparison-card');
  const container = q('#analysis-comparison-content');
  if (!card || !container || allComps.length < 2) {
    if (card) card.style.display = 'none';
    return;
  }
  card.style.display = '';
  const maxFollowers = Math.max(...allComps.map(c => c.followers || 0), 1);
  const comparisonText = buildCompetitorComparisonText(allComps);
  container.innerHTML = `<div style="display:flex;flex-direction:column;gap:10px">
    ${allComps.map(c => {
      const pct = Math.round(((c.followers||0) / maxFollowers) * 100);
      const delta = c.delta || 0;
      const isOwn = c.is_own;
      return `<div>
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;font-size:13px">
          <span style="font-weight:${isOwn?700:500}">@${esc(c.username)}${isOwn?' (você)':''}</span>
          <span style="color:var(--text-2)">${formatNum(c.followers||0)} seguidores
            ${delta!==0?`<span style="color:${delta>0?'var(--success)':'var(--danger)'}"> ${delta>0?'+':''}${formatNum(delta)}</span>`:''}
          </span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${isOwn?'var(--primary)':'var(--text-muted)'}"></div></div>
      </div>`;
    }).join('')}
  </div>
  <div class="card" style="margin-top:16px;background:var(--surface-2)">
    <div class="card-title">Comparativo textual</div>
    <div style="white-space:pre-wrap;font-size:13px;line-height:1.6">${esc(comparisonText)}</div>
  </div>`;
}

function buildCompetitorComparisonText(allComps) {
  const own = allComps.find(c => c.is_own);
  const comps = allComps.filter(c => !c.is_own).sort((a, b) => (b.followers || 0) - (a.followers || 0));
  if (!own || !comps.length) return 'Adicione concorrentes para gerar o comparativo.';
  const leader = comps[0];
  const closest = [...comps].sort((a, b) => Math.abs((a.followers || 0) - (own.followers || 0)) - Math.abs((b.followers || 0) - (own.followers || 0)))[0];
  const ownDiagnosis = own.analysis?.diagnosis?.positioning_verdict || '';
  const leaderDiagnosis = leader.analysis?.diagnosis?.positioning_verdict || '';
  const ownPosition = own.analysis?.strategy?.new_positioning || own.analysis?.header?.subtitle || '';
  const leaderPosition = leader.analysis?.strategy?.new_positioning || leader.analysis?.header?.subtitle || '';
  const gap = (leader.followers || 0) - (own.followers || 0);
  const parts = [
    `Perfil principal: @${own.username} com ${formatNum(own.followers || 0)} seguidores.`,
    `Concorrente líder: @${leader.username} com ${formatNum(leader.followers || 0)} seguidores${gap > 0 ? `, uma diferença de ${formatNum(gap)} seguidores.` : '.'}`,
    closest ? `Concorrente mais próximo em tamanho: @${closest.username} com ${formatNum(closest.followers || 0)} seguidores.` : '',
    ownDiagnosis ? `Leitura do seu perfil: ${ownDiagnosis}` : '',
    leaderDiagnosis ? `Leitura do concorrente líder: ${leaderDiagnosis}` : '',
    ownPosition ? `Seu posicionamento recomendado: ${ownPosition}` : '',
    leaderPosition ? `Posicionamento do líder: ${leaderPosition}` : '',
  ].filter(Boolean);
  return parts.join('\n\n');
}

function _hasInstaScraperSession() {
  if (S._instaDefaultSession) return true;
  if (S._instaLoginSession) return true;
  if (S._instaSessionCount > 0) return true;
  return false;
}

async function fetchOwnProfile() {
  const username = getInstaScrapeUsername();
  if (!username) {
    q('#analysis-own-content').innerHTML = '<div class="alert alert-error">Defina o handle no Brand Profile (Handle Instagram) ou vincule o Instagram da página na Meta. O login do scrapper (homeunity) é só o cookies — não confunda com o @ a analisar.</div>';
    return;
  }
  if (!_hasInstaScraperSession()) {
    q('#analysis-own-content').innerHTML = '<div class="alert alert-error">Não há ficheiro em <code>instascrapper/sessions/</code> no servidor. Rode: <code>python3 instascrapper/main.py login homeunity &lt;senha&gt;</code> (login do browser = homeunity). O botão acima puxa <strong>@' + esc(username) + '</strong>, não o homeunity.</div>';
    return;
  }
  q('#analysis-own-content').innerHTML = '<div class="loading-state"><div class="spinner"></div>Buscando @' + esc(username) + '…</div>';
  setBtnLoading('#btn-fetch-profile', true, 'Buscando...');
  const r = await api('/panel/insta/profile', { method: 'POST', body: JSON.stringify({ username, page_id: S.client.page_id, as_user: '' }), _timeout: 140000 });
  setBtnLoading('#btn-fetch-profile', false, 'Atualizar dados');
  if (r.ok) {
    await db_add_own_if_needed(username);
    await loadAnalysisOwn();
  } else {
    q('#analysis-own-content').innerHTML = `<div class="alert alert-error">${esc(r.error||'Erro ao buscar perfil. Verifique se a sessão está ativa.')}</div>`;
  }
}

async function db_add_own_if_needed(username) {
  // Add as own profile if not already tracked
  await post('/panel/insta/add-competitor', {
    page_id: S.client.page_id, username, is_own: true,
    label: S.client.name,
  });
}

async function analyzeOwnProfile() {
  const username = getInstaScrapeUsername();
  if (!username) {
    q('#analysis-own-content').innerHTML = '<div class="alert alert-error">Defina o @ no Brand (Handle Instagram) ou vincule o Instagram na Meta.</div>';
    return;
  }
  if (!_hasInstaScraperSession()) {
    q('#analysis-own-content').innerHTML = '<div class="alert alert-error">Sem sessão do instascrapper no servidor. Faça login na CLI (ver "Atualizar dados"). A leitura usa a sessão do ficheiro (ex. homeunity), não a seleção de perfil do painel.</div>';
    return;
  }
  q('#analysis-own-content').innerHTML = '<div class="loading-state"><div class="spinner-lg spinner"></div><div><div style="font-weight:600">Analisando com IA...</div><div style="font-size:12px;color:var(--text-muted);margin-top:4px">Isso pode levar 1-2 minutos</div></div></div>';
  setBtnLoading('#btn-analyze-own', true, 'Analisando...');
  await post('/panel/insta/add-competitor', { page_id: S.client.page_id, username, is_own: true, label: S.client.name });
  const r = await api('/panel/insta/analyze', { method: 'POST', body: JSON.stringify({ username, page_id: S.client.page_id, as_user: '' }), _timeout: 200000 });
  setBtnLoading('#btn-analyze-own', false, 'Analisar com IA');
  S._instaRunDiagnostics = r.diagnostics || S._instaRunDiagnostics;
  if (r.ok) {
    await loadAnalysisOwn();
  } else {
    const login = (S._instaLoginSession || 'homeunity').replace(/^@/, '');
    const alvo = getInstaScrapeUsername() || 'perfil (Brand/Meta)';
    const msg = r.error === 'instagram_session_expired'
      ? (r.detail || `Sessão de login do scrapper (@${login}) expirou. Rode no servidor: python3 instascrapper/main.py login ${login} <senha>. O alvo a analisar @${alvo} é o Instagram da página, não a conta de login.`)
      : (r.error || r.detail || 'Erro na análise.');
    q('#analysis-own-content').innerHTML = `${renderInstaRunDiagnosticsCard(S._instaRunDiagnostics)}<div class="alert alert-error" style="margin-top:8px">${esc(msg)}</div>`;
  }
}

async function analyzeCompetitor(username) {
  if (!_hasInstaScraperSession()) {
    q('#analysis-own-content').innerHTML = '<div class="alert alert-error">Sem sessão do instascrapper no servidor.</div>';
    return;
  }
  const btn = q(`#btn-analyze-comp-${username}`);
  if (btn) { btn.disabled = true; btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px"></div>'; }
  const r = await api('/panel/insta/analyze', { method: 'POST', body: JSON.stringify({ username, page_id: S.client.page_id, as_user: '' }), _timeout: 200000 });
  if (r.ok) await loadAnalysisCompetitors();
  else if (btn) { btn.disabled = false; btn.textContent = 'Analisar'; }
}

function _ensureCompareFlyout() {
  let el = q('#insta-compare-flyout');
  if (el) return el;
  el = document.createElement('div');
  el.id = 'insta-compare-flyout';
  el.setAttribute('style', 'position:fixed;bottom:16px;right:16px;max-width:min(480px,96vw);max-height:80vh;overflow:auto;z-index:700;padding:0;border-radius:16px;box-shadow:0 12px 48px rgba(0,0,0,.2);background:var(--bg);border:1px solid var(--border)');
  document.body.appendChild(el);
  return el;
}

function renderCompareHtml(cmp) {
  if (!cmp || typeof cmp !== 'object') return '<p>Sem dados.</p>';
  const li = (arr) => (Array.isArray(arr) ? arr : []).map((t) => `<li>${esc(t)}</li>`).join('');
  return `
    <div style="padding:16px 18px 20px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px">
        <div style="font-size:16px;font-weight:700">Comparativo com concorrente</div>
        <button type="button" class="btn btn-ghost btn-sm" onclick="q('#insta-compare-flyout')?.remove()">×</button>
      </div>
      ${cmp.resumo_numeros ? `<p style="font-size:13px;line-height:1.55;margin-bottom:12px">${esc(cmp.resumo_numeros)}</p>` : ''}
      <div class="grid2" style="gap:10px">
        <div class="card" style="padding:10px">
          <div class="card-title" style="font-size:12px">Vantagens dele</div>
          <ul style="margin:0;padding-left:18px;font-size:12px">${li(cmp.vantagens_concorrente)}</ul>
        </div>
        <div class="card" style="padding:10px">
          <div class="card-title" style="font-size:12px">Os seus pontos fortes</div>
          <ul style="margin:0;padding-left:18px;font-size:12px">${li(cmp.vantagens_meu_perfil)}</ul>
        </div>
      </div>
      ${(cmp.desvantagens_meu_perfil && cmp.desvantagens_meu_perfil.length) ? `<div class="card" style="padding:10px;margin-top:10px">
        <div class="card-title" style="font-size:12px">O que apertar no seu perfil</div>
        <ul style="margin:0;padding-left:18px;font-size:12px">${li(cmp.desvantagens_meu_perfil)}</ul>
      </div>` : ''}
      <div class="card" style="padding:10px;margin-top:10px;background:var(--primary-light)">
        <div class="card-title" style="font-size:12px">O que fazer agora</div>
        <ul style="margin:0;padding-left:18px;font-size:12px;font-weight:500">${li(cmp.o_que_fazer)}</ul>
      </div>
      ${cmp.sintese_estrategica ? `<p style="font-size:13px;line-height:1.5;margin-top:10px"><strong>Prioridade:</strong> ${esc(cmp.sintese_estrategica)}</p>` : ''}
    </div>`;
}

async function compareCompetitorToOwn(username) {
  if (!S.client?.page_id) return;
  const box = _ensureCompareFlyout();
  box.innerHTML = '<div style="padding:20px"><div class="loading-state"><div class="spinner"></div>Gerando comparativo com IA…</div></div>';
  const r = await post('/panel/insta/compare', { page_id: S.client.page_id, competitor_username: username });
  if (!r.ok) {
    box.innerHTML = `<div style="padding:16px"><button type="button" class="btn btn-ghost btn-sm" style="float:right" onclick="this.closest('#insta-compare-flyout')?.remove()">×</button><div class="alert alert-error">${esc(r.detail || r.error || 'Erro no comparativo.')}</div></div>`;
    return;
  }
  box.innerHTML = renderCompareHtml(r.compare || {});
}

async function singlePostTestGenerate() {
  if (!S.client?.page_id) {
    q('#sp-alert').innerHTML = mkAlert('error', 'Selecione uma empresa na barra lateral.');
    return;
  }
  const theme = (q('#sp-theme') && q('#sp-theme').value) ? q('#sp-theme').value.trim() : '';
  const imageSource = q('#sp-image-source')?.value || 'ai';
  const selectedImageUrl = (q('#sp-image-url')?.value || '').trim();
  const wrap = q('#sp-preview-wrap');
  const alert = q('#sp-alert');
  if (alert) alert.innerHTML = '';
  if (wrap) wrap.style.display = 'block';
  if (q('#sp-image-prompt')) q('#sp-image-prompt').value = '';
  if (q('#sp-preview-box')) q('#sp-preview-box').innerHTML = '<div class="loading-state"><div class="spinner"></div>Gerando legenda e imagem…</div>';
  const imageFocus = (q('#sp-image-focus')?.value || '').trim();
  const r = await post('/panel/single-content/generate', { page_id: S.client.page_id, theme, image_source: imageSource, selected_image_url: selectedImageUrl, image_focus: imageFocus });
  if (!r.ok) {
    if (q('#sp-caption')) q('#sp-caption').value = r.caption || '';
    if (q('#sp-title')) q('#sp-title').value = r.title || '';
    if (q('#sp-subtitle')) q('#sp-subtitle').value = r.subtitle || '';
    if (q('#sp-image-prompt')) q('#sp-image-prompt').value = r.image_prompt || '';
    if (q('#sp-preview-box')) {
      q('#sp-preview-box').innerHTML = renderSinglePostPreview({
        imageUrl: '',
        caption: r.caption || '',
        theme,
        title: r.title || '',
        subtitle: r.subtitle || '',
        logoUrl: '',
        imagePrompt: r.image_prompt || '',
        clientName: S.client?.name || '',
        igUsername: S.client?.ig_username || '',
        imageError: r.detail || r.error || 'Falha ao gerar imagem',
      });
    }
    if (alert) alert.innerHTML = mkAlert('error', (r.detail || r.error || '') + (r.caption ? ' Legenda: ' + r.caption.substring(0, 200) : ''));
    return;
  }
  if (q('#sp-caption')) q('#sp-caption').value = r.caption || '';
  if (q('#sp-title')) q('#sp-title').value = r.title || '';
  if (q('#sp-subtitle')) q('#sp-subtitle').value = r.subtitle || '';
  if (q('#sp-image-prompt')) q('#sp-image-prompt').value = r.image_prompt || '';
  if (q('#sp-image-url')) q('#sp-image-url').value = r.public_url || '';
  if (q('#sp-preview-box')) {
    q('#sp-preview-box').innerHTML = renderSinglePostPreview({
      imageUrl: r.public_url || '',
      caption: r.caption || '',
      theme,
      title: r.title || '',
      subtitle: r.subtitle || '',
      logoUrl: r.logo_url || '',
      imagePrompt: r.image_prompt || '',
      clientName: S.client?.name || '',
      igUsername: S.client?.ig_username || '',
    });
  }
  if (wrap) wrap.style.display = 'block';
  if (alert) alert.innerHTML = mkAlert('success', 'Copy e imagem geradas. Revise abaixo antes de agendar ou postar.');
}

async function singlePostSchedule() {
  if (!S.client?.page_id) { q('#sp-alert').innerHTML = mkAlert('error', 'Selecione uma empresa.'); return; }
  const cap = (q('#sp-caption') && q('#sp-caption').value) || '';
  const imageUrl = (q('#sp-image-url') && q('#sp-image-url').value) || '';
  const dt = q('#sp-schedule-dt') && q('#sp-schedule-dt').value;
  const channels = getSinglePostChannels();
  if (!imageUrl || !cap) { q('#sp-alert').innerHTML = mkAlert('error', 'Gere o post antes de agendar.'); return; }
  if (!dt) { q('#sp-alert').innerHTML = mkAlert('error', 'Escolha data e hora.'); return; }
  if (!channels.length) { q('#sp-alert').innerHTML = mkAlert('error', 'Selecione ao menos um canal para agendar.'); return; }
  const scheduled_at = Math.floor(new Date(dt).getTime() / 1000);
  if (!scheduled_at) { q('#sp-alert').innerHTML = mkAlert('error', 'Data inválida.'); return; }
  const results = [];
  if (channels.includes('instagram')) {
    results.push(await post('/scheduled/posts', { channel: 'instagram', page_id: S.client.page_id, image_url: imageUrl, caption: cap, scheduled_at }));
  }
  if (channels.includes('facebook')) {
    results.push(await post('/meta/facebook/photo', { page_id: S.client.page_id, image_url: imageUrl, caption: cap, published: false, scheduled_publish_time: String(scheduled_at) }));
  }
  const failed = results.find(r => !r.ok);
  q('#sp-alert').innerHTML = failed
    ? mkAlert('error', failed.error || failed.detail || 'Falha ao agendar')
    : mkAlert('success', `Agendado com sucesso em: ${channels.join(', ')}.`);
}

async function singlePostPublishNow() {
  if (!S.client?.page_id) { q('#sp-alert').innerHTML = mkAlert('error', 'Selecione uma empresa.'); return; }
  const cap = (q('#sp-caption') && q('#sp-caption').value) || '';
  const imageUrl = (q('#sp-image-url') && q('#sp-image-url').value) || '';
  const channels = getSinglePostChannels();
  if (!imageUrl || !cap) { q('#sp-alert').innerHTML = mkAlert('error', 'Gere o post antes de publicar.'); return; }
  if (!channels.length) { q('#sp-alert').innerHTML = mkAlert('error', 'Selecione ao menos um canal para publicar.'); return; }
  const results = [];
  if (channels.includes('instagram')) {
    results.push(await post('/meta/instagram/post', { page_id: S.client.page_id, image_url: imageUrl, caption: cap, publish_now: true }));
  }
  if (channels.includes('facebook')) {
    results.push(await post('/meta/facebook/photo', { page_id: S.client.page_id, image_url: imageUrl, caption: cap, published: true }));
  }
  const failed = results.find(r => !r.ok);
  q('#sp-alert').innerHTML = failed
    ? mkAlert('error', (failed.error || '') + ' ' + (failed.detail || JSON.stringify(failed.detail || '')))
    : mkAlert('success', `Enviado com sucesso para: ${channels.join(', ')}.`);
}

function renderSinglePostPreview({ imageUrl = '', caption = '', theme = '', title = '', subtitle = '', logoUrl = '', imagePrompt = '', clientName = '', igUsername = '', imageError = '' } = {}) {
  return `
    ${imageError ? `<div class="alert alert-error" style="margin-bottom:10px">${esc(imageError)}</div>` : ''}
    <div style="padding:12px;border:1px solid var(--border);border-radius:16px;background:var(--surface);display:flex;justify-content:center;align-items:center;min-height:420px">
      ${imageUrl ? `<img src="${esc(imageUrl)}" alt="Preview do post" style="display:block;max-width:100%;max-height:520px;border-radius:12px;border:1px solid var(--border)" />` : `<div style="color:var(--text-muted)">Sem imagem</div>`}
    </div>`;
}

async function saveSinglePostDraft() {
  if (!S.client?.page_id) { q('#sp-alert').innerHTML = mkAlert('error', 'Selecione uma empresa.'); return; }
  const theme = (q('#sp-theme')?.value || '').trim();
  const imageFocus = (q('#sp-image-focus')?.value || '').trim();
  const caption = (q('#sp-caption')?.value || '').trim();
  const title = (q('#sp-title')?.value || '').trim();
  const subtitle = (q('#sp-subtitle')?.value || '').trim();
  const imagePrompt = (q('#sp-image-prompt')?.value || '').trim();
  const imageUrl = (q('#sp-image-url')?.value || '').trim();
  const suggestedAt = q('#sp-schedule-dt')?.value || '';
  if (!theme && !caption && !title && !imagePrompt) {
    q('#sp-alert').innerHTML = mkAlert('error', 'Preencha ou gere algum conteúdo antes de salvar o rascunho.');
    return;
  }
  const [suggested_date, suggested_time] = suggestedAt ? suggestedAt.split('T') : ['', ''];
  const post = {
    title: title || theme || 'Conteúdo avulso',
    theme: theme || title || 'Conteúdo avulso',
    format: 'feed',
    suggested_date: suggested_date || '',
    suggested_time: suggested_time || '19:00',
    brief: subtitle || '',
    image_focus: imageFocus,
    caption,
    image_url: imageUrl,
    image_prompt: imagePrompt,
    status: 'draft',
  };
  const now = new Date();
  const titleLabel = title || theme || `Conteúdo avulso ${now.toLocaleDateString('pt-BR')}`;
  const r = await postJsonSingleDraft({
    plan_id: '',
    page_id: S.client.page_id,
    page_name: S.client.name,
    ig_user_id: S.client.ig_user_id,
    ig_username: S.client.ig_username,
    posts: [post],
    focus: theme || '',
    title: titleLabel,
    plan_type: 'single',
    month_label: '',
  });
  q('#sp-alert').innerHTML = r.ok ? mkAlert('success', 'Rascunho salvo em Conteúdo.') : mkAlert('error', `Erro ao salvar rascunho: ${r.detail || r.error || 'falha desconhecida'}`);
}

function postJsonSingleDraft(body) {
  return post('/panel/content-plan/save', body);
}

async function loadSinglePostGallery(force = false) {
  const list = q('#sp-gallery-list');
  if (!list) return;
  if (!force && list.dataset.loaded === '1') return;
  list.innerHTML = '<div class="loading-state"><div class="spinner"></div>Carregando galeria...</div>';
  const r = await api('/panel/gallery');
  if (!r.ok) {
    list.innerHTML = `<div class="alert alert-error">${esc(r.error || 'Erro ao carregar galeria.')}</div>`;
    return;
  }
  const imgs = Array.isArray(r.images) ? r.images : [];
  list.dataset.loaded = '1';
  if (!imgs.length) {
    list.innerHTML = '<div class="empty-state"><p>Nenhuma imagem na galeria ainda.</p></div>';
    return;
  }
  const selected = (q('#sp-image-url')?.value || '').trim();
  list.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px">${imgs.slice(0, 60).map(img => `
    <button type="button" onclick="selectSinglePostGalleryImage(${JSON.stringify(img.public_url)})" style="padding:0;border:2px solid ${selected === img.public_url ? 'var(--primary)' : 'var(--border)'};border-radius:12px;background:var(--surface);overflow:hidden;cursor:pointer">
      <img src="${esc(img.public_url)}" alt="${esc(img.filename || 'imagem')}" style="width:100%;aspect-ratio:1;object-fit:cover;display:block" />
    </button>`).join('')}</div>`;
}

function selectSinglePostGalleryImage(url) {
  if (q('#sp-image-url')) q('#sp-image-url').value = url || '';
  loadSinglePostGallery(true);
}

function handleSinglePostImageSourceChange() {
  const source = q('#sp-image-source')?.value || 'ai';
  q('#sp-gallery-wrap')?.classList.toggle('hidden', source !== 'gallery');
  q('#sp-upload-wrap')?.classList.toggle('hidden', source !== 'upload');
  if (source === 'gallery') loadSinglePostGallery();
}

async function uploadSinglePostImage() {
  const file = q('#sp-upload-file')?.files?.[0];
  if (!file) {
    q('#sp-alert').innerHTML = mkAlert('error', 'Selecione uma imagem para upload.');
    return;
  }
  const fd = new FormData();
  fd.append('file', file);
  const resp = await fetch('/panel/gallery/upload-image', { method: 'POST', body: fd });
  const r = await resp.json().catch(() => ({ ok: false, error: 'invalid_json' }));
  if (!r.ok) {
    q('#sp-alert').innerHTML = mkAlert('error', r.detail || r.error || 'Falha no upload.');
    return;
  }
  if (q('#sp-image-url')) q('#sp-image-url').value = r.public_url || '';
  q('#sp-alert').innerHTML = mkAlert('success', 'Imagem enviada. Agora gere a copy/preview.');
}

function openAddCompetitorModal() {
  q('#competitor-username').value = '';
  q('#competitor-label').value = '';
  q('#add-competitor-alert').innerHTML = '';
  openModal('modal-add-competitor');
}

async function addCompetitor() {
  const username = q('#competitor-username').value.trim().replace('@', '');
  const label = q('#competitor-label').value.trim();
  const analyzeNow = q('#competitor-analyze-now')?.checked;
  if (!username) { q('#add-competitor-alert').innerHTML = mkAlert('error', 'Digite um username.'); return; }
  setBtnLoading('#btn-add-competitor-confirm', true, 'Adicionando...');
  await post('/panel/insta/add-competitor', { page_id: S.client.page_id, username, label, is_own: false });
  closeModal('modal-add-competitor');
  setBtnLoading('#btn-add-competitor-confirm', false, 'Adicionar');
  if (analyzeNow) {
    await loadAnalysisCompetitors();
    await analyzeCompetitor(username);
  } else {
    await loadAnalysisCompetitors();
  }
}

async function removeCompetitor(username) {
  if (!confirm(`Remover @${username} dos concorrentes?`)) return;
  await post('/panel/insta/remove-competitor', { page_id: S.client.page_id, username });
  loadAnalysisCompetitors();
}

async function showAnalysisModal(username) {
  q('#analysis-modal-title').textContent = `Análise · @${username}`;
  q('#analysis-modal-body').innerHTML = '<div class="loading-state"><div class="spinner"></div>Carregando análise...</div>';
  openModal('modal-analysis');
  const r = await api(`/panel/insta/competitors?page_id=${S.client.page_id}`);
  if (r && r.ok) {
    S._competitorsCache = r.competitors || [];
  }
  const comps = S._competitorsCache || [];
  const comp = comps.find(c => String(c.username || '').toLowerCase() === String(username || '').toLowerCase());
  if (!comp) {
    q('#analysis-modal-body').innerHTML = '<div class="empty-state"><p>Perfil não encontrado na lista atual.</p></div>';
    return;
  }
  const analysis = comp.analysis || {};
  const profile = comp.profile || {};
  q('#analysis-modal-body').innerHTML = renderAnalysisHTML(username, profile, analysis);
}

function _coherenceColor(v) {
  if (!v) return 'var(--text-muted)';
  const l = String(v).toLowerCase();
  if (l.includes('alto')) return 'var(--success)';
  if (l.includes('baixo')) return 'var(--danger)';
  return 'var(--warning)';
}

function renderPostsAnalysisSection(pa, profile) {
  if (!pa || typeof pa !== 'object') return '';
  const score = pa.consistency_score;
  const label = pa.consistency_label || '';
  const scorePct = Math.min(100, Math.max(0, (score || 0) * 10));
  const scoreColor = score >= 7 ? 'var(--success)' : score >= 4 ? 'var(--warning)' : 'var(--danger)';

  // Monta mapa de image_url por filename usando recent_posts / selected_posts
  const imgMap = {};
  const postSrc = Array.isArray(profile.selected_posts) ? profile.selected_posts
    : Array.isArray(profile.recent_posts) ? profile.recent_posts : [];
  postSrc.forEach((p, i) => {
    if (p.filename) imgMap[p.filename] = { url: p.image_url || '', caption: p.caption || '', permalink: p.permalink || '' };
    // fallback por índice
    imgMap[`post_${String(i+1).padStart(2,'0')}.jpg`] = imgMap[`post_${String(i+1).padStart(2,'0')}.jpg`] || { url: p.image_url || '', caption: p.caption || '', permalink: p.permalink || '' };
    imgMap[`pinned_${String(i+1).padStart(2,'0')}.jpg`] = imgMap[`pinned_${String(i+1).padStart(2,'0')}.jpg`] || { url: p.image_url || '', caption: p.caption || '', permalink: p.permalink || '' };
  });

  const positives = Array.isArray(pa.positives) ? pa.positives : [];
  const improvements = Array.isArray(pa.improvements) ? pa.improvements : [];
  const posts = Array.isArray(pa.posts) ? pa.posts : [];

  const postsHTML = posts.map((p, i) => {
    const ref = p.ref || '';
    const imgData = imgMap[ref] || postSrc[i] && { url: postSrc[i].image_url || '', caption: postSrc[i].caption || '', permalink: postSrc[i].permalink || '' } || {};
    const imgUrl = imgData.url || '';
    const captionRaw = imgData.caption || p.caption_summary || '';
    const permalink = imgData.permalink || '';
    const coherenceColor = _coherenceColor(p.coherence);
    return `<div style="display:flex;gap:12px;padding:12px 0;border-bottom:1px solid var(--border)">
      <div style="flex-shrink:0;width:80px;height:80px;border-radius:10px;overflow:hidden;background:var(--surface-2);border:1px solid var(--border)">
        ${imgUrl ? `<${permalink ? `a href="${esc(permalink)}" target="_blank" rel="noopener"` : 'div'} style="display:block;width:100%;height:100%"><img src="${esc(imgUrl)}" alt="" style="width:100%;height:100%;object-fit:cover" loading="lazy" onerror="this.parentElement.style.background='var(--surface-2)'"/></${permalink ? 'a' : 'div'}>` : ''}
      </div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">
          <span style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase">${esc(p.type||'')}</span>
          ${p.coherence ? `<span style="font-size:11px;font-weight:600;color:${coherenceColor};background:${coherenceColor}1a;padding:1px 6px;border-radius:4px">Coerência: ${esc(p.coherence)}</span>` : ''}
        </div>
        ${captionRaw ? `<div style="font-size:12px;color:var(--text-2);line-height:1.4;margin-bottom:6px;font-style:italic">"${esc(String(captionRaw).slice(0,120))}${captionRaw.length>120?'…':''}"</div>` : ''}
        ${p.what_works ? `<div style="font-size:12px;margin-bottom:3px">✓ <span style="color:var(--success)">${esc(p.what_works)}</span></div>` : ''}
        ${p.what_to_improve ? `<div style="font-size:12px">↑ <span style="color:var(--text-2)">${esc(p.what_to_improve)}</span></div>` : ''}
      </div>
    </div>`;
  }).join('');

  return `<div class="card mb-16">
    <div class="card-title">Análise dos últimos posts</div>
    ${pa.overview ? `<p style="font-size:13px;color:var(--text-2);line-height:1.55;margin:0 0 14px">${esc(pa.overview)}</p>` : ''}
    ${score != null ? `<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
      <div style="font-size:12px;font-weight:700;color:var(--text-muted);white-space:nowrap">Consistência</div>
      <div style="flex:1;height:6px;background:var(--surface-2);border-radius:99px;overflow:hidden">
        <div style="width:${scorePct}%;height:100%;background:${scoreColor};border-radius:99px;transition:width .4s"></div>
      </div>
      <div style="font-size:13px;font-weight:700;color:${scoreColor};white-space:nowrap">${score}/10 ${label ? `· ${esc(label)}` : ''}</div>
    </div>` : ''}
    ${pa.pattern_verdict ? `<div style="font-size:13px;font-weight:600;margin-bottom:14px;padding:10px 12px;background:var(--surface-2);border-radius:var(--r-sm);border-left:3px solid var(--primary)">${esc(pa.pattern_verdict)}</div>` : ''}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
      ${positives.length ? `<div>
        <div style="font-size:11px;font-weight:700;color:var(--success);text-transform:uppercase;margin-bottom:6px">Pontos positivos</div>
        ${positives.map(x=>`<div style="font-size:12px;padding:3px 0;border-bottom:1px solid var(--border)">✓ ${esc(x)}</div>`).join('')}
      </div>` : ''}
      ${improvements.length ? `<div>
        <div style="font-size:11px;font-weight:700;color:var(--warning);text-transform:uppercase;margin-bottom:6px">A melhorar</div>
        ${improvements.map(x=>`<div style="font-size:12px;padding:3px 0;border-bottom:1px solid var(--border)">↑ ${esc(x)}</div>`).join('')}
      </div>` : ''}
    </div>
    ${pa.caption_quality ? `<div style="font-size:12px;color:var(--text-2);margin-bottom:12px"><strong>Legendas:</strong> ${esc(pa.caption_quality)}</div>` : ''}
    ${postsHTML}
  </div>`;
}

function renderAnalysisHTML(username, profile, analysis) {
  if (!Object.keys(analysis).length) return `<div class="empty-state"><p>Análise não disponível. Clique em "Analisar" para gerar.</p></div>`;
  const h = analysis.header || {};
  const diag = analysis.diagnosis || {};
  const strat = analysis.strategy || {};
  const icp = analysis.icp || {};
  const pa = analysis.posts_analysis || null;
  const stats = h.stats || {};
  const profPic = profile.avatar_url || profile.profile_pic_url || profile.profile_picture_url || '';
  const textSummary = buildAnalysisTextSummary(username, analysis);

  return `
    <div style="display:flex;gap:14px;align-items:center;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid var(--border)">
      ${profPic ? `<img src="${profPic}" style="width:56px;height:56px;border-radius:50%;object-fit:cover;flex-shrink:0"/>` : ''}
      <div>
        <div style="font-size:16px;font-weight:700">@${esc(username)}</div>
        <div style="font-size:13px;color:var(--text-muted);margin-top:2px">${esc(h.subtitle||'')}</div>
        <div style="display:flex;gap:16px;margin-top:8px">
          ${stats.followers ? `<span><strong>${esc(stats.followers)}</strong> seguidores</span>` : ''}
          ${stats.posts ? `<span><strong>${esc(stats.posts)}</strong> posts</span>` : ''}
          ${stats.engagement_rate ? `<span><strong>${esc(stats.engagement_rate)}</strong> engajamento</span>` : ''}
        </div>
      </div>
    </div>
    ${renderPostsAnalysisSection(pa, profile)}
    <div class="card mb-16">
      <div class="card-title">Diagnóstico completo</div>
      <div style="white-space:pre-wrap;font-size:13px;line-height:1.6">${esc(textSummary)}</div>
    </div>
    ${diag.positioning_verdict ? `<div class="card mb-16" style="background:var(--primary-light);border-color:#C7D2FE">
      <div class="card-title">Diagnóstico</div>
      <div style="font-size:14px;color:var(--primary-text);font-weight:500">${esc(diag.positioning_verdict)}</div>
      ${diag.central_problem ? `<div style="font-size:13px;color:var(--text-2);margin-top:8px">${esc(diag.central_problem)}</div>` : ''}
    </div>` : ''}
    ${icp.primary_title ? `<div class="card mb-16">
      <div class="card-title">Público-alvo (ICP)</div>
      <div style="font-size:14px;font-weight:600;margin-bottom:4px">${esc(icp.primary_title)}</div>
      <div style="font-size:13px;color:var(--text-2)">${esc(icp.primary_demographics||'')}</div>
      ${Array.isArray(icp.pains) ? `<div style="margin-top:10px"><div style="font-size:12px;font-weight:700;color:var(--text-muted);margin-bottom:6px">DORES</div>${icp.pains.map(p=>`<div style="font-size:13px;padding:4px 0;border-bottom:1px solid var(--border)">· ${esc(p)}</div>`).join('')}</div>` : ''}
    </div>` : ''}
    ${strat.new_positioning ? `<div class="card mb-16">
      <div class="card-title">Estratégia recomendada</div>
      <div style="font-size:14px;font-weight:500;color:var(--text)">${esc(strat.new_positioning)}</div>
      ${Array.isArray(strat.bio_versions) && strat.bio_versions.length ? `<div style="margin-top:12px"><div class="card-title">Bio sugerida</div><div style="font-size:13px;font-family:monospace;background:var(--bg);padding:10px;border-radius:var(--r-sm);white-space:pre-wrap">${esc((strat.bio_versions[0]?.content||'').replace(/\\n/g,'\n'))}</div></div>` : ''}
    </div>` : ''}
  `;
}

function buildAnalysisTextSummary(username, analysis) {
  const h = analysis.header || {};
  const diag = analysis.diagnosis || {};
  const strat = analysis.strategy || {};
  const icp = analysis.icp || {};
  const parts = [
    `Perfil analisado: @${username}`,
    h.subtitle ? `Resumo: ${h.subtitle}` : '',
    diag.positioning_verdict ? `Diagnóstico: ${diag.positioning_verdict}` : '',
    diag.central_problem ? `Problema central: ${diag.central_problem}` : '',
    icp.primary_title ? `Público principal: ${icp.primary_title}` : '',
    icp.primary_demographics ? `Demografia: ${icp.primary_demographics}` : '',
    Array.isArray(icp.pains) && icp.pains.length ? `Principais dores: ${icp.pains.join('; ')}` : '',
    strat.new_positioning ? `Posicionamento recomendado: ${strat.new_positioning}` : '',
    Array.isArray(strat.bio_versions) && strat.bio_versions.length ? `Bio sugerida: ${(strat.bio_versions[0]?.content || '').replace(/\\n/g, ' ')}` : '',
  ].filter(Boolean);
  return parts.join('\n\n');
}

/* ── UTILS ─────────────────────────────────────────────────── */
function q(sel) { return document.querySelector(sel); }
function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function mkAlert(type, msg) { return `<div class="alert alert-${type}">${esc(msg)}</div>`; }
function formatNum(n) {
  const v = parseFloat(String(n||'0').replace(/[^0-9.-]/g,''));
  if (isNaN(v)) return String(n);
  if (v>=1000000) return (v/1000000).toFixed(1)+'M';
  if (v>=1000) return (v/1000).toFixed(1)+'K';
  return String(Math.round(v));
}
function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts*1000).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',year:'2-digit',hour:'2-digit',minute:'2-digit'});
}
function fmtDateLong(d) {
  if (!d) return '—';
  try { return new Date(d+'T00:00:00').toLocaleDateString('pt-BR',{weekday:'long',day:'numeric',month:'long'}); }
  catch { return d; }
}
function setBtnLoading(sel, loading, label) {
  const btn = q(sel); if (!btn) return;
  btn.disabled = loading;
  btn.innerHTML = loading ? `<div class="spinner" style="width:14px;height:14px;border-width:2px"></div>${label}` : label;
}
function openModal(id) { q(`#${id}`)?.classList.add('open'); }
function closeModal(id) { q(`#${id}`)?.classList.remove('open'); }
document.addEventListener('click', e => { if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open'); });
document.addEventListener('DOMContentLoaded', init);

function showAlert(id, msg, type) {
  const el = q(`#${id}`);
  if (!el) return;
  el.innerHTML = msg ? (type === 'info' ? `<div class="alert alert-info">${msg}</div>` : mkAlert(type, msg)) : '';
}

/* ── AGENTS SECTION ────────────────────────────────────────── */
const S_AGENTS = { config: null, designerTab: 'template' };

const AGENT_ICONS = {
  copy_generation: '✍️',
  prompt_generation: '🎨',
  plan_generation: '📅',
  focus_suggestion: '🎯',
  brand_analysis: '🏷️',
  campaign_analysis: '📊',
  profile_analysis: '📈',
  icp_analysis: '👤',
};
const AGENT_NAMES = {
  copy_generation: 'Redator',
  prompt_generation: 'Diretor de Arte',
  plan_generation: 'Planejador',
  focus_suggestion: 'Analista de Foco',
  brand_analysis: 'Analista de Marca',
  campaign_analysis: 'Analista de Campanhas',
  profile_analysis: 'Analista de Perfil',
  icp_analysis: 'Analista de ICP',
};
const AGENT_DESCS = {
  copy_generation: 'Gera legendas do Instagram com gancho, desenvolvimento e CTA.',
  prompt_generation: 'Gera as variáveis que preenchem o template de arte.',
  plan_generation: 'Cria planos de conteúdo mensais com temas e datas.',
  focus_suggestion: 'Sugere o foco estratégico para cada post ou plano.',
  brand_analysis: 'Analisa o perfil e posicionamento da marca.',
  campaign_analysis: 'Analisa resultados de campanhas de tráfego e leads.',
  profile_analysis: 'Analisa o perfil do Instagram e desempenho orgânico.',
  icp_analysis: 'Define e refina o cliente ideal da marca.',
};

async function loadAgentsSection() {
  clearAgentsSection();
  if (S_AGENTS.config) { renderAgentsSection(S_AGENTS.config); return; }
  const pid = S.client?.page_id || '';
  const data = await api(`/panel/agents/config${pid ? '?page_id=' + encodeURIComponent(pid) : ''}`);
  if (!data.ok) { showAlert('agents-alert', data.error || 'Erro ao carregar agentes', 'error'); return; }
  S_AGENTS.config = data;
  renderAgentsSection(data);
}

function clearAgentsSection() {
  if (q('#agents-image-template')) q('#agents-image-template').value = '';
  if (q('#agents-prompt-generation-note')) q('#agents-prompt-generation-note').value = '';
  if (q('#agents-preview-briefing')) q('#agents-preview-briefing').value = '';
  if (q('#agents-preview-prompt-text')) q('#agents-preview-prompt-text').value = '';
  if (q('#agents-preview-alert')) q('#agents-preview-alert').innerHTML = '';
  if (q('#agents-preview-result')) q('#agents-preview-result').classList.add('hidden');
  if (q('#agents-preview-image-box')) q('#agents-preview-image-box').innerHTML = '<span class="muted">Sem imagem</span>';
  if (q('#agents-others-list')) q('#agents-others-list').innerHTML = '';
  renderAgentRefs([]);
  renderAgentGallery([]);
}

function renderAgentsSection(data) {
  if (q('#agents-image-template')) q('#agents-image-template').value = data.image_template || '';
  if (q('#agents-instagram-source') && !q('#agents-instagram-source').value) {
    q('#agents-instagram-source').value = S.client?.ig_username ? `@${S.client.ig_username}` : '';
  }
  renderAgentRefs(data.designer_references || [], data.visual_references || []);
  renderAgentGallery(data.gallery_references || []);
  // Brand context in Diretor de Arte tab
  const colors = data.brand_colors || [];
  const icp = (data.icp_summary || '').trim();
  const ctx = q('#agents-brand-context');
  if (ctx) {
    if (colors.length || icp) {
      ctx.style.display = 'block';
      const colorsRow = q('#agents-brand-colors-row');
      if (colorsRow) {
        if (colors.length) {
          colorsRow.innerHTML = '<span class="muted" style="font-size:12px">Cores:</span>'
            + colors.map(c => `<span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:${esc(c)};border:1px solid rgba(0,0,0,.15)" title="${esc(c)}"></span><span style="font-size:11px;color:var(--text-muted)">${esc(c)}</span>`).join('');
        } else {
          colorsRow.innerHTML = '';
        }
      }
      const icpRow = q('#agents-icp-summary-row');
      if (icpRow) icpRow.textContent = icp ? `ICP: ${icp}` : '';
    } else {
      ctx.style.display = 'none';
    }
  }
  const others = (data.agents || []).filter(a => a.key !== 'prompt_generation');
  const list = q('#agents-others-list');
  if (!list) return;
  list.innerHTML = others.map(a => `
    <div class="card" style="padding:18px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <div style="font-size:22px">${AGENT_ICONS[a.key] || '🤖'}</div>
        <div>
          <div style="font-size:14px;font-weight:700">${AGENT_NAMES[a.key] || a.key}</div>
          <div class="muted" style="font-size:12px">${AGENT_DESCS[a.key] || ''}</div>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">Instruções extras</label>
        <textarea id="agent-note-${a.key}" class="form-textarea" rows="5" placeholder="Instruções adicionais para este agente (opcional). Ex: sempre usar linguagem formal, focar em ROI...">${a.system_note || ''}</textarea>
      </div>
      <div class="mt-8"><button class="btn btn-primary btn-sm" onclick="saveAgentNote('${a.key}', 'agent-note-${a.key}')">Salvar</button></div>
    </div>
  `).join('');
  const directorNote = (data.agents || []).find(a => a.key === 'prompt_generation');
  if (q('#agents-prompt-generation-note')) q('#agents-prompt-generation-note').value = directorNote?.system_note || '';
}

function renderAgentRefs(refs, visualRefs) {
  const grid = q('#agents-refs-grid');
  if (!grid) return;
  const brandRefs = (visualRefs || []).filter(r => r.url);
  const hasRefs = refs.length || brandRefs.length;
  if (!hasRefs) { grid.innerHTML = '<div class="muted">Nenhuma referência enviada ainda.</div>'; return; }
  const refsHtml = refs.map(r => `
    <div style="position:relative;border-radius:10px;overflow:hidden;border:1px solid var(--border)">
      <img src="${r.url}" style="width:100%;aspect-ratio:1;object-fit:cover;display:block" />
      <div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.55);padding:4px 8px;display:flex;justify-content:space-between;align-items:center">
        <span style="color:#fff;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:80px">${r.original_name || r.filename || ''}</span>
        <button onclick="deleteAgentRef('${r.id}')" style="background:none;border:none;color:#f87171;cursor:pointer;font-size:14px;padding:0">✕</button>
      </div>
    </div>
  `).join('');
  const brandRefsHtml = brandRefs.length ? `
    <div style="grid-column:1/-1;margin-top:${refs.length ? 16 : 0}px">
      <div class="muted mb-8" style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Referências de Configurações</div>
    </div>
    ${brandRefs.map(r => `
      <div style="position:relative;border-radius:10px;overflow:hidden;border:1px solid var(--border);opacity:.85">
        <img src="${r.url || r.path || ''}" style="width:100%;aspect-ratio:1;object-fit:cover;display:block" />
        <div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.45);padding:3px 6px">
          <span style="color:#fff;font-size:9px">${esc(r.label || r.kind || 'referência')}</span>
        </div>
      </div>
    `).join('')}
  ` : '';
  grid.innerHTML = refsHtml + brandRefsHtml;
}

function switchAgentsDesignerTab(tab, el) {
  S_AGENTS.designerTab = tab;
  document.querySelectorAll('.agents-designer-tab').forEach(t => t.classList.add('hidden'));
  q(`#agents-designer-${tab}`)?.classList.remove('hidden');
  document.querySelectorAll('#sec-agents .card:first-of-type .tab-btn').forEach(b => b.classList.remove('active'));
  el?.classList.add('active');
}

async function saveAgentNote(key, textareaId) {
  const note = (q(`#${textareaId}`)?.value || '').trim();
  const pid = S.client?.page_id || '';
  const data = await post('/panel/agents/config', { key, system_note: note, ...(pid ? { page_id: pid } : {}) });
  if (data.ok) {
    if (S_AGENTS.config) {
      const agent = (S_AGENTS.config.agents || []).find(a => a.key === key);
      if (agent) agent.system_note = note;
    }
    showAlert('agents-alert', 'Instruções salvas.', 'success');
  } else {
    showAlert('agents-alert', data.error || 'Erro ao salvar', 'error');
  }
}

async function saveAgentImageTemplate() {
  const value = q('#agents-image-template')?.value || '';
  const pid = S.client?.page_id || '';
  const data = await post('/panel/agents/config', { key: 'image_template', value, ...(pid ? { page_id: pid } : {}) });
  if (data.ok) {
    if (S_AGENTS.config) S_AGENTS.config.image_template = value;
    showAlert('agents-alert', 'Template salvo.', 'success');
  } else {
    showAlert('agents-alert', data.error || 'Erro ao salvar template', 'error');
  }
}

function resetAgentImageTemplate() {
  if (!confirm('Restaurar o template padrão? Você perderá as edições atuais.')) return;
  const pid = S.client?.page_id || '';
  post('/panel/agents/config', { key: 'image_template', value: '', ...(pid ? { page_id: pid } : {}) }).then(data => {
    if (data.ok) {
      S_AGENTS.config = null;
      loadAgentsSection();
      showAlert('agents-alert', 'Template restaurado ao padrão.', 'success');
    }
  });
}

async function uploadAgentReferences() {
  const input = q('#agents-ref-file');
  if (!input?.files?.length) { showAlert('agents-alert', 'Selecione ao menos uma imagem.', 'error'); return; }
  const pid = S.client?.page_id || '';
  let uploaded = 0;
  for (const file of input.files) {
    const fd = new FormData();
    fd.append('file', file);
    if (pid) fd.append('page_id', pid);
    const res = await fetch('/panel/agents/designer/upload-reference', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      uploaded++;
      if (S_AGENTS.config) {
        S_AGENTS.config.designer_references = S_AGENTS.config.designer_references || [];
        S_AGENTS.config.designer_references.push({ id: data.id, url: data.url, filename: data.url.split('/').pop(), original_name: file.name });
      }
    }
  }
  if (uploaded) {
    input.value = '';
    renderAgentRefs(S_AGENTS.config?.designer_references || []);
    showAlert('agents-alert', `${uploaded} referência(s) enviada(s).`, 'success');
  }
}

async function importAgentReferencesFromInstagram() {
  const pid = S.client?.page_id || '';
  if (!pid) { showAlert('agents-alert', 'Selecione uma empresa primeiro.', 'error'); return; }
  const raw = (q('#agents-instagram-source')?.value || '').trim();
  const username = raw.replace(/^@+/, '').trim() || (S.client?.ig_username || '').trim();
  if (!username) { showAlert('agents-alert', 'Informe um Instagram para importar.', 'error'); return; }
  showAlert('agents-alert', '<div class="spinner" style="display:inline-block;width:12px;height:12px;border-width:2px;vertical-align:middle"></div> Importando posts do Instagram como referências...', 'info');
  const r = await api('/panel/agents/designer/import-instagram', { method: 'POST', body: JSON.stringify({ page_id: pid, username }), _timeout: 200000 });
  if (!r.ok) { showAlert('agents-alert', r.error || 'Erro ao importar referências do Instagram', 'error'); return; }
  if (S_AGENTS.config) {
    S_AGENTS.config.designer_references = r.designer_references || [];
  }
  renderAgentRefs(r.designer_references || []);
  showAlert('agents-alert', `${r.imported_count || 0} post(s) importado(s) de @${username} como referência visual.`, 'success');
}

async function deleteAgentRef(refId) {
  if (!confirm('Remover esta referência?')) return;
  const pid = S.client?.page_id || '';
  const url = `/panel/agents/designer/reference/${refId}${pid ? '?page_id=' + encodeURIComponent(pid) : ''}`;
  const res = await fetch(url, { method: 'DELETE' });
  const data = await res.json();
  if (data.ok && S_AGENTS.config) {
    S_AGENTS.config.designer_references = (S_AGENTS.config.designer_references || []).filter(r => r.id !== refId);
    renderAgentRefs(S_AGENTS.config.designer_references);
  }
}

function renderAgentGallery(refs) {
  const grid = q('#agents-gallery-grid');
  if (!grid) return;
  if (!refs.length) { grid.innerHTML = '<div class="muted">Nenhuma foto enviada ainda.</div>'; return; }
  grid.innerHTML = refs.map(r => `
    <div style="border-radius:10px;overflow:hidden;border:1px solid var(--border);background:var(--surface)">
      <div style="position:relative">
        <img src="${r.url}" style="width:100%;aspect-ratio:1;object-fit:cover;display:block" />
        <button onclick="deleteAgentGallery('${r.id}')" style="position:absolute;top:4px;right:4px;background:rgba(0,0,0,.55);border:none;color:#f87171;cursor:pointer;font-size:14px;padding:2px 6px;border-radius:4px">✕</button>
      </div>
      <div style="padding:6px 8px">
        <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.original_name || r.filename || ''}</div>
        <textarea id="gallery-desc-${r.id}" rows="2" style="width:100%;font-size:11px;resize:vertical;border:1px solid var(--border);border-radius:4px;padding:4px;background:var(--surface-alt,#f7f7f8);color:var(--text)" placeholder="Descreva o que há nesta foto...">${r.description || ''}</textarea>
        <div style="display:flex;gap:4px;margin-top:4px">
          <button onclick="saveGalleryDesc('${r.id}')" style="flex:1;font-size:10px;padding:3px 6px;border:1px solid var(--border);border-radius:4px;cursor:pointer;background:var(--surface)">Salvar</button>
          <button onclick="autoDescribeGallery('${r.id}')" style="flex:1;font-size:10px;padding:3px 6px;border:1px solid var(--primary,#6366f1);border-radius:4px;cursor:pointer;background:var(--surface);color:var(--primary,#6366f1)" title="Descrever com IA">✨ IA</button>
        </div>
      </div>
    </div>
  `).join('');
}

async function uploadAgentGallery() {
  const input = q('#agents-gallery-file');
  if (!input?.files?.length) { showAlert('agents-alert', 'Selecione ao menos uma foto.', 'error'); return; }
  const pid = S.client?.page_id || '';
  if (!pid) { showAlert('agents-alert', 'Selecione uma empresa primeiro.', 'error'); return; }
  showAlert('agents-alert', '<div class="spinner" style="display:inline-block;width:12px;height:12px;border-width:2px;vertical-align:middle"></div> Enviando e descrevendo fotos...', 'info');
  let uploaded = 0;
  for (const file of input.files) {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('page_id', pid);
    const res = await fetch('/panel/agents/designer/upload-gallery', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      uploaded++;
      if (S_AGENTS.config) {
        S_AGENTS.config.gallery_references = S_AGENTS.config.gallery_references || [];
        S_AGENTS.config.gallery_references.push({ id: data.id, url: data.url, filename: data.url.split('/').pop(), original_name: file.name, description: data.description || '' });
      }
    }
  }
  if (uploaded) {
    input.value = '';
    renderAgentGallery(S_AGENTS.config?.gallery_references || []);
    showAlert('agents-alert', `${uploaded} foto(s) enviada(s) com descrição automática.`, 'success');
  }
}

async function deleteAgentGallery(refId) {
  if (!confirm('Remover esta foto da galeria?')) return;
  const pid = S.client?.page_id || '';
  if (!pid) return;
  const url = `/panel/agents/designer/gallery/${refId}?page_id=${encodeURIComponent(pid)}`;
  const res = await fetch(url, { method: 'DELETE' });
  const data = await res.json();
  if (data.ok && S_AGENTS.config) {
    S_AGENTS.config.gallery_references = (S_AGENTS.config.gallery_references || []).filter(r => r.id !== refId);
    renderAgentGallery(S_AGENTS.config.gallery_references);
  }
}

async function saveGalleryDesc(refId) {
  const pid = S.client?.page_id || '';
  if (!pid) return;
  const desc = (q(`#gallery-desc-${refId}`)?.value || '').trim();
  const res = await fetch(`/panel/agents/designer/gallery/${refId}?page_id=${encodeURIComponent(pid)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description: desc }),
  });
  const data = await res.json();
  if (data.ok && S_AGENTS.config) {
    const ref = (S_AGENTS.config.gallery_references || []).find(r => r.id === refId);
    if (ref) ref.description = desc;
    showAlert('agents-alert', 'Descrição salva.', 'success');
  }
}

async function autoDescribeGallery(refId) {
  const pid = S.client?.page_id || '';
  if (!pid) return;
  const btn = document.querySelector(`[onclick="autoDescribeGallery('${refId}')"]`);
  if (btn) { btn.textContent = '...'; btn.disabled = true; }
  const res = await fetch(`/panel/agents/designer/gallery/${refId}?page_id=${encodeURIComponent(pid)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto: true }),
  });
  const data = await res.json();
  if (btn) { btn.textContent = '✨ IA'; btn.disabled = false; }
  if (data.ok) {
    const ta = q(`#gallery-desc-${refId}`);
    if (ta) ta.value = data.description || '';
    if (S_AGENTS.config) {
      const ref = (S_AGENTS.config.gallery_references || []).find(r => r.id === refId);
      if (ref) ref.description = data.description || '';
    }
    showAlert('agents-alert', 'Descrição gerada pela IA.', 'success');
  }
}

async function agentPreviewPrompt() {
  const briefing = (q('#agents-preview-briefing')?.value || '').trim();
  if (!briefing) { showAlert('agents-preview-alert', 'Preencha o briefing de teste.', 'error'); return; }
  showAlert('agents-preview-alert', '<div class="spinner" style="display:inline-block;width:14px;height:14px;border-width:2px;vertical-align:middle"></div> Gerando prévia...', 'info');
  const pid = S.client?.page_id || '';
  const data = await api('/panel/agents/designer/preview-prompt', { method: 'POST', body: JSON.stringify({ description: briefing, ...(pid ? { page_id: pid } : {}) }), _timeout: 60000 });
  if (!data.ok) { showAlert('agents-preview-alert', data.error || 'Erro ao gerar prévia', 'error'); return; }
  showAlert('agents-preview-alert', '', '');
  q('#agents-preview-result')?.classList.remove('hidden');
  if (q('#agents-preview-prompt-text')) q('#agents-preview-prompt-text').value = data.image_prompt || '';
}

async function agentTestImage() {
  const briefing = (q('#agents-preview-briefing')?.value || '').trim();
  if (!briefing) { showAlert('agents-preview-alert', 'Preencha o briefing de teste.', 'error'); return; }
  showAlert('agents-preview-alert', '<div class="spinner" style="display:inline-block;width:14px;height:14px;border-width:2px;vertical-align:middle"></div> Gerando imagem...', 'info');
  const pid = S.client?.page_id || '';
  const previewData = await api('/panel/agents/designer/preview-prompt', { method: 'POST', body: JSON.stringify({ description: briefing, ...(pid ? { page_id: pid } : {}) }), _timeout: 60000 });
  if (!previewData.ok) { showAlert('agents-preview-alert', previewData.error || 'Erro ao gerar prompt', 'error'); return; }
  q('#agents-preview-result')?.classList.remove('hidden');
  if (q('#agents-preview-prompt-text')) q('#agents-preview-prompt-text').value = previewData.image_prompt || '';
  await _agentGenerateImageFromPrompt(previewData.image_prompt || '');
}

async function agentTestImageFromPreview() {
  const prompt = (q('#agents-preview-prompt-text')?.value || '').trim();
  if (!prompt) { showAlert('agents-preview-alert', 'Nenhum prompt para gerar imagem.', 'error'); return; }
  showAlert('agents-preview-alert', '<div class="spinner" style="display:inline-block;width:14px;height:14px;border-width:2px;vertical-align:middle"></div> Gerando imagem...', 'info');
  await _agentGenerateImageFromPrompt(prompt);
}

async function _agentGenerateImageFromPrompt(prompt) {
  const pid = S.client?.page_id || '';
  const data = await api('/panel/agents/designer/test-image', { method: 'POST', body: JSON.stringify({ image_prompt: prompt, ...(pid ? { page_id: pid } : {}) }), _timeout: 180000 });
  const box = q('#agents-preview-image-box');
  if (!data.ok) {
    showAlert('agents-preview-alert', data.error || 'Erro ao gerar imagem', 'error');
    return;
  }
  showAlert('agents-preview-alert', '', '');
  const url = data.url || data.image_url || data.public_url || '';
  if (url && box) {
    box.innerHTML = `<img src="${url}" style="max-width:100%;max-height:480px;border-radius:10px;display:block" />`;
  } else if (box) {
    box.innerHTML = '<div class="muted">Imagem gerada mas URL não disponível.</div>';
  }
}

/* ── ONBOARDING ─────────────────────────────────────────────── */
function openOnboarding() {
  if (!S.client?.page_id) { alert('Selecione uma empresa primeiro.'); return; }
  q('#onb-step-1').style.display = '';
  q('#onb-step-2').style.display = 'none';
  q('#onb-step-3').style.display = 'none';
  q('#onb-alert').innerHTML = '';
  q('#onb-website').value = '';
  q('#onb-instagram').value = S.client.ig_username ? '@' + S.client.ig_username : '';
  q('#onb-description').value = '';
  if (q('#onb-reference-websites')) q('#onb-reference-websites').value = '';
  if (q('#onb-reference-instagrams')) q('#onb-reference-instagrams').value = '';
  if (q('#onb-logo-file')) q('#onb-logo-file').value = '';
  if (q('#onb-logo-light-file')) q('#onb-logo-light-file').value = '';
  if (q('#onb-visual-reference-file')) q('#onb-visual-reference-file').value = '';
  openModal('modal-onboarding');
}

function onbBack() {
  q('#onb-step-3').style.display = 'none';
  q('#onb-step-1').style.display = '';
}

async function runOnboarding() {
  const website = (q('#onb-website')?.value || '').trim();
  const instagram = (q('#onb-instagram')?.value || '').trim();
  const description = (q('#onb-description')?.value || '').trim();
  const referenceWebsites = (q('#onb-reference-websites')?.value || '').split('\n').map(v => v.trim()).filter(Boolean);
  const referenceInstagrams = (q('#onb-reference-instagrams')?.value || '').split('\n').map(v => v.replace('@', '').trim()).filter(Boolean);
  if (!website && !instagram && !description) {
    q('#onb-alert').innerHTML = mkAlert('error', 'Preencha ao menos o site ou o Instagram.');
    return;
  }
  const pid = S.client.page_id;
  const logoFile = q('#onb-logo-file')?.files?.[0];
  const logoLightFile = q('#onb-logo-light-file')?.files?.[0];
  const refFiles = Array.from(q('#onb-visual-reference-file')?.files || []);
  q('#onb-step-1').style.display = 'none';
  q('#onb-step-2').style.display = '';
  const msgs = [
    'Organizando referências da marca...',
    'Analisando site e gerando perfil...',
    'Buscando informações do negócio...',
    'Analisando logos, cores e referências visuais...',
    'Identificando público e concorrentes...',
    'Montando ICP, direção de arte e instruções dos agentes...',
    'Quase pronto...',
  ];
  let mi = 0;
  const ticker = setInterval(() => { const el = q('#onb-loading-msg'); if (el && mi < msgs.length - 1) el.textContent = msgs[++mi]; }, 3000);
  try {
    if (logoFile) {
      const fd = new FormData();
      fd.append('page_id', pid);
      fd.append('file', logoFile);
      fd.append('variant', 'dark');
      const upl = await (await fetch('/panel/brand-profile/upload-logo', { method: 'POST', body: fd })).json();
      if (!upl.ok) throw new Error(upl.error || 'Erro ao enviar logo principal');
    }
    if (logoLightFile) {
      const fd = new FormData();
      fd.append('page_id', pid);
      fd.append('file', logoLightFile);
      fd.append('variant', 'light');
      const upl = await (await fetch('/panel/brand-profile/upload-logo', { method: 'POST', body: fd })).json();
      if (!upl.ok) throw new Error(upl.error || 'Erro ao enviar logo para fundo escuro');
    }
    if (refFiles.length) {
      const fd = new FormData();
      fd.append('page_id', pid);
      fd.append('kind', 'brand_reference');
      refFiles.forEach(file => fd.append('files', file));
      const upl = await (await fetch('/panel/brand-profile/upload-visual-reference', { method: 'POST', body: fd })).json();
      if (!upl.ok) throw new Error(upl.error || 'Erro ao enviar referências visuais');
      const vis = await post('/panel/brand-profile/analyze-visual-references', { page_id: pid });
      if (!vis.ok) throw new Error(vis.detail || vis.error || 'Erro ao analisar referências visuais');
    }
  } catch (err) {
    clearInterval(ticker);
    q('#onb-step-2').style.display = 'none';
    q('#onb-step-1').style.display = '';
    q('#onb-alert').innerHTML = mkAlert('error', err?.message || 'Erro ao preparar referências da marca.');
    return;
  }
  const r = await api('/panel/onboarding/analyze', {
    method: 'POST',
    body: JSON.stringify({
      page_id: pid,
      website_url: website,
      instagram_handle: instagram.replace('@', ''),
      description,
      reference_websites: referenceWebsites,
      reference_instagrams: referenceInstagrams,
    }),
    _timeout: 180000,
  });
  clearInterval(ticker);
  if (!r.ok) {
    q('#onb-step-2').style.display = 'none';
    q('#onb-step-1').style.display = '';
    q('#onb-alert').innerHTML = mkAlert('error', r.error || 'Erro ao analisar. Tente novamente.');
    return;
  }
  const p = r.profile || {};
  q('#onb-brand-name').value  = p.brand_name || '';
  q('#onb-tagline').value     = p.tagline || '';
  q('#onb-tone').value        = p.tone || '';
  q('#onb-audience').value    = p.target_audience || '';
  q('#onb-visual-style').value = p.visual_style || '';
  q('#onb-best-offer').value  = p.best_offer || '';
  q('#onb-desc-out').value    = p.description || '';
  q('#onb-products').value    = p.key_products || '';
  q('#onb-competitors').value = Array.isArray(p.competitors) ? p.competitors.join(', ') : (p.competitors || '');
  q('#onb-colors').value = Array.isArray(p.colors) ? p.colors.join(', ') : (p.colors || '');
  q('#onb-font-preference').value = p.font_preference || '';
  q('#onb-reference-style-prompt').value = p.reference_style_prompt || '';
  q('#onb-icp-pains').value   = p.icp_pain_points || '';
  q('#onb-icp-desires').value = p.icp_desires || '';
  q('#onb-icp-objections').value = p.icp_objections || '';
  q('#onb-icp-summary').value = p.icp_summary || '';
  q('#onb-step-2').style.display = 'none';
  q('#onb-step-3').style.display = '';
}

async function saveOnboarding() {
  const profile = {
    brand_name:      (q('#onb-brand-name')?.value   || '').trim(),
    tagline:         (q('#onb-tagline')?.value       || '').trim(),
    tone:            (q('#onb-tone')?.value          || '').trim(),
    target_audience: (q('#onb-audience')?.value      || '').trim(),
    visual_style:    (q('#onb-visual-style')?.value  || '').trim(),
    best_offer:      (q('#onb-best-offer')?.value    || '').trim(),
    description:     (q('#onb-desc-out')?.value      || '').trim(),
    key_products:    (q('#onb-products')?.value      || '').trim(),
    colors:          (q('#onb-colors')?.value        || '').trim(),
    font_preference: (q('#onb-font-preference')?.value || '').trim(),
    reference_style_prompt: (q('#onb-reference-style-prompt')?.value || '').trim(),
  };
  const icp = {
    icp_pain_points: (q('#onb-icp-pains')?.value      || '').trim(),
    icp_desires:     (q('#onb-icp-desires')?.value     || '').trim(),
    icp_objections:  (q('#onb-icp-objections')?.value  || '').trim(),
    icp_summary:     (q('#onb-icp-summary')?.value     || '').trim(),
  };
  const r = await post('/panel/onboarding/save', { page_id: S.client.page_id, profile, icp });
  if (r.ok) {
    S.brandProfile = { ...(S.brandProfile || {}), ...profile };
    S_AGENTS.config = null;
    closeModal('modal-onboarding');
    // Reload settings to show new values
    loadSettings();
    showAlert('brand-alert', 'Perfil preenchido com IA e salvo!', 'success');
  } else {
    alert('Erro ao salvar: ' + (r.error || 'desconhecido'));
  }
}

/* ── AGENTS AI ADJUST ───────────────────────────────────────── */
async function adjustAgentsWithAI() {
  const pid = S.client?.page_id || '';
  if (!pid) { showAlert('agents-alert', 'Selecione uma empresa primeiro.', 'error'); return; }
  const btn = q('#btn-agents-adjust-ai');
  if (btn) { btn.textContent = '...'; btn.disabled = true; }
  showAlert('agents-alert', '<div class="spinner" style="display:inline-block;width:14px;height:14px;border-width:2px;vertical-align:middle"></div> Gerando template e instruções personalizadas para todos os agentes...', 'info');
  const r = await api('/panel/agents/adjust-with-ai', { method: 'POST', body: JSON.stringify({ page_id: pid }), _timeout: 180000 });
  if (btn) { btn.textContent = '✨ Ajustar todos com IA'; btn.disabled = false; }
  if (!r.ok) { showAlert('agents-alert', r.error || 'Erro ao ajustar agentes', 'error'); return; }
  // Update textareas
  if (r.image_template && q('#agents-image-template')) {
    q('#agents-image-template').value = r.image_template;
    if (S_AGENTS.config) S_AGENTS.config.image_template = r.image_template;
  }
  if (r.director_note && q('#agents-prompt-generation-note')) {
    q('#agents-prompt-generation-note').value = r.director_note;
    if (S_AGENTS.config) {
      const ag = (S_AGENTS.config.agents || []).find(a => a.key === 'prompt_generation');
      if (ag) ag.system_note = r.director_note;
    }
  }
  if (r.agent_notes && S_AGENTS.config) {
    Object.entries(r.agent_notes).forEach(([key, note]) => {
      const ta = q(`#agent-note-${key}`);
      if (ta) ta.value = note || '';
      const ag = (S_AGENTS.config.agents || []).find(item => item.key === key);
      if (ag) ag.system_note = note || '';
    });
  }
  showAlert('agents-alert', 'Agentes ajustados para esta empresa. Revise e refine se quiser.', 'success');
  // Switch to template tab so user can see the result
  const tplBtn = document.querySelector('#sec-agents .card:first-of-type .tab-btn');
  if (tplBtn) switchAgentsDesignerTab('template', tplBtn);
}

async function adjustArtWithAI() {
  const pid = S.client?.page_id || '';
  if (!pid) { showAlert('agents-alert', 'Selecione uma empresa primeiro.', 'error'); return; }
  const btn = q('#btn-agents-adjust-art');
  if (btn) { btn.textContent = '...'; btn.disabled = true; }
  showAlert('agents-alert', '<div class="spinner" style="display:inline-block;width:14px;height:14px;border-width:2px;vertical-align:middle"></div> Gerando template e instruções do Diretor de Arte...', 'info');
  const r = await api('/panel/agents/adjust-art-with-ai', { method: 'POST', body: JSON.stringify({ page_id: pid }), _timeout: 120000 });
  if (btn) { btn.textContent = '🎨 Gerar só arte'; btn.disabled = false; }
  if (!r.ok) { showAlert('agents-alert', r.error || 'Erro ao gerar agente de arte', 'error'); return; }
  if (r.image_template && q('#agents-image-template')) {
    q('#agents-image-template').value = r.image_template;
    if (S_AGENTS.config) S_AGENTS.config.image_template = r.image_template;
  }
  if (r.director_note && q('#agents-prompt-generation-note')) {
    q('#agents-prompt-generation-note').value = r.director_note;
    if (S_AGENTS.config) {
      const ag = (S_AGENTS.config.agents || []).find(a => a.key === 'prompt_generation');
      if (ag) ag.system_note = r.director_note;
    }
  }
  showAlert('agents-alert', 'Template e Diretor de Arte gerados. Revise e refine se quiser.', 'success');
  const dirBtn = document.querySelectorAll('#sec-agents .card:first-of-type .tab-btn')[2];
  if (dirBtn) switchAgentsDesignerTab('director', dirBtn);
}
