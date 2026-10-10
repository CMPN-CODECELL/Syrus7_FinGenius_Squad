// State Store
const state = {
  currentTab: 'dashboard',
  visibility: 'discoverable',
  trackedCount: 3,
  
  opportunities: [
    { id: 1, title: 'AI Climate Hackathon 2026', category: 'Hackathon', duration: 'Weekend', fee: 'Free', format: 'Remote', sustainability: 'Yes', match: 98, desc: 'Build autonomous agents to analyze carbon footprint datasets.', deadline: '3 days left' },
    { id: 2, title: 'Green Tech Innovation Summit', category: 'Competition', duration: '2 Weeks', fee: 'Free', format: 'Hybrid', sustainability: 'Yes', match: 94, desc: 'Pitch eco-friendly software prototypes to industry leaders.', deadline: '5 days left' },
    { id: 3, title: 'Open Source Synergy Sprint', category: 'Workshop', duration: 'Weekend', fee: 'Free', format: 'Remote', sustainability: 'No', match: 89, desc: 'Collaborative development for peer-to-peer learning tools.', deadline: '1 week left' },
    { id: 4, title: 'CleanEnergy AI Research Grant', category: 'Research', duration: '1 Month', fee: 'Free', format: 'In-Person', sustainability: 'Yes', match: 86, desc: 'Research grant for optimizing smart grid distribution.', deadline: '2 weeks left' }
  ],

  peers: [
    { name: 'Elena Rostova', role: 'AI / ML Specialist', skills: ['Python', 'PyTorch', 'LangChain'], synergy: '98%' },
    { name: 'Marcus Chen', role: 'UI/UX & Frontend Lead', skills: ['React', 'Tailwind CSS', 'Figma'], synergy: '93%' },
    { name: 'Sarah Jenkins', role: 'Climate Data Analyst', skills: ['Data Modeling', 'Python', 'GIS'], synergy: '91%' }
  ],

  logs: [
    "[SYSTEM] Agent initialized. Embedded profile vectorized.",
    "[CRAWLER] Polled 4 public hackathon platforms.",
    "[REASONING] Calculated 98% fit for 'AI Climate Hackathon 2026'."
  ]
};

// DOM Init
document.addEventListener('DOMContentLoaded', () => {
  renderDashboard();
  renderOpportunities();
  renderPeers();
});

// Tab Switcher
function switchTab(tabId) {
  state.currentTab = tabId;
  
  const views = ['dashboard', 'discover', 'peers', 'profile', 'agent'];
  views.forEach(v => {
    const el = document.getElementById(`view-${v}`);
    if (el) el.classList.add('hidden');
    
    const navBtn = document.getElementById(`nav-${v}`);
    if (navBtn) navBtn.classList.remove('tab-active');
  });

  const activeView = document.getElementById(`view-${tabId}`);
  if (activeView) activeView.classList.remove('hidden');

  const activeNav = document.getElementById(`nav-${tabId}`);
  if (activeNav) activeNav.classList.add('tab-active');
}

// Render Dashboard
function renderDashboard() {
  const recList = document.getElementById('dashboardRecommendedList');
  const deadlineList = document.getElementById('deadlineList');

  if (recList) {
    recList.innerHTML = state.opportunities.slice(0, 3).map(opp => `
      <div class="card-glass p-5 rounded-2xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20">${opp.category}</span>
            <span class="text-xs text-brand-400 font-semibold">${opp.match}% Match</span>
          </div>
          <h3 class="font-semibold text-white text-base">${opp.title}</h3>
          <p class="text-xs text-gray-400 mt-1">${opp.desc}</p>
        </div>
        <button onclick="trackDeadline('${opp.title}')" class="bg-brand-500 hover:bg-brand-400 text-black font-bold text-xs px-4 py-2 rounded-xl shrink-0 transition">
          Track Task
        </button>
      </div>
    `).join('');
  }

  if (deadlineList) {
    deadlineList.innerHTML = state.opportunities.slice(0, 3).map(opp => `
      <div class="flex items-center justify-between p-3 bg-dark-900/60 rounded-xl border border-white/5 text-xs">
        <div>
          <div class="font-medium text-white">${opp.title}</div>
          <div class="text-gray-400 text-[11px]">${opp.deadline}</div>
        </div>
        <span class="text-brand-400 font-bold">Active</span>
      </div>
    `).join('');
  }
}

// Filter Opportunities
function filterOpportunities() {
  const query = (document.getElementById('searchInput')?.value || '').toLowerCase();
  const cat = document.getElementById('filterCategory')?.value || 'all';
  const dur = document.getElementById('filterDuration')?.value || 'all';
  const fee = document.getElementById('filterFee')?.value || 'all';
  const fmt = document.getElementById('filterFormat')?.value || 'all';
  const sus = document.getElementById('filterSustainability')?.value || 'all';

  const filtered = state.opportunities.filter(o => {
    const matchesSearch = o.title.toLowerCase().includes(query) || o.desc.toLowerCase().includes(query);
    const matchesCat = cat === 'all' || o.category === cat;
    const matchesDur = dur === 'all' || o.duration === dur;
    const matchesFee = fee === 'all' || o.fee === fee;
    const matchesFmt = fmt === 'all' || o.format === fmt;
    const matchesSus = sus === 'all' || o.sustainability === sus;
    return matchesSearch && matchesCat && matchesDur && matchesFee && matchesFmt && matchesSus;
  });

  renderOpportunities(filtered);
}

// Render Opportunities Grid
function renderOpportunities(list = state.opportunities) {
  const grid = document.getElementById('opportunityGrid');
  if (!grid) return;

  grid.innerHTML = list.map(opp => `
    <div class="card-glass p-6 rounded-2xl flex flex-col justify-between">
      <div>
        <div class="flex justify-between items-start mb-3">
          <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20">${opp.category}</span>
          <span class="text-xs font-bold text-brand-400 bg-brand-500/10 px-2 py-0.5 rounded-md">${opp.match}% Fit</span>
        </div>
        <h3 class="text-base font-semibold text-white mb-2">${opp.title}</h3>
        <p class="text-xs text-gray-400 mb-4">${opp.desc}</p>
      </div>

      <div class="pt-4 border-t border-white/10 flex items-center justify-between text-xs">
        <span class="text-gray-400">${opp.deadline}</span>
        <button onclick="openModal('${opp.title}', '${opp.desc}')" class="bg-white/10 hover:bg-white/20 text-white font-medium px-3.5 py-1.5 rounded-xl transition">
          Details
        </button>
      </div>
    </div>
  `).join('');
}

// Render Peers
function renderPeers() {
  const grid = document.getElementById('peerGrid');
  const notice = document.getElementById('peerNoticePrivate');

  if (state.visibility === 'private') {
    if (grid) grid.classList.add('hidden');
    if (notice) notice.classList.remove('hidden');
    return;
  }

  if (notice) notice.classList.add('hidden');
  if (grid) {
    grid.classList.remove('hidden');
    grid.innerHTML = state.peers.map(peer => `
      <div class="card-glass p-6 rounded-2xl">
        <div class="flex justify-between items-start mb-3">
          <div>
            <h3 class="font-semibold text-white text-base">${peer.name}</h3>
            <p class="text-xs text-brand-400">${peer.role}</p>
          </div>
          <span class="text-xs bg-brand-500/10 text-brand-400 font-bold px-2.5 py-1 rounded-full border border-brand-500/20">${peer.synergy} Synergy</span>
        </div>
        <div class="flex flex-wrap gap-1.5 mb-6">
          ${peer.skills.map(s => `<span class="text-[10px] bg-dark-900 text-gray-300 px-2.5 py-1 rounded-md border border-white/5">${s}</span>`).join('')}
        </div>
        <button onclick="openModal('Invite Sent', 'Connection request sent to ${peer.name}.')" class="w-full bg-brand-500 hover:bg-brand-400 text-black font-bold text-xs py-2.5 rounded-xl transition">
          Send Team Request
        </button>
      </div>
    `).join('');
  }
}

// Visibility Controls
function setPeerVisibility(mode) {
  state.visibility = mode;
  const headerToggle = document.getElementById('headerPrivacyToggle');
  if (headerToggle) headerToggle.value = mode;

  const btnDisc = document.getElementById('peerVisDiscoverable');
  const btnPriv = document.getElementById('peerVisPrivate');

  if (mode === 'discoverable') {
    if (btnDisc) btnDisc.className = "px-3 py-1 rounded-lg text-xs font-semibold bg-brand-500 text-black";
    if (btnPriv) btnPriv.className = "px-3 py-1 rounded-lg text-xs font-semibold text-gray-400 hover:text-white";
  } else {
    if (btnPriv) btnPriv.className = "px-3 py-1 rounded-lg text-xs font-semibold bg-brand-500 text-black";
    if (btnDisc) btnDisc.className = "px-3 py-1 rounded-lg text-xs font-semibold text-gray-400 hover:text-white";
  }

  renderPeers();
}

function updatePrivacyMode(val) {
  setPeerVisibility(val === 'private' ? 'private' : 'discoverable');
}

// Profile Controls
function updateSkillVal(key, val) {
  const target = document.getElementById(`val-${key}`);
  if (target) target.innerText = `Level ${val}`;
}

function saveProfile() {
  openModal('Profile Updated', 'Your skills and sustainability matching preferences have been saved.');
}

// Task & Modal System
function trackDeadline(title) {
  state.trackedCount++;
  const el = document.getElementById('trackedCount');
  if (el) el.innerText = state.trackedCount;
  openModal('Task Tracked', `Added "${title}" to your active deadline tracker.`);
}

function triggerAgentRun() {
  const consoleLog = document.getElementById('agentConsoleLog');
  if (consoleLog) {
    const timestamp = new Date().toLocaleTimeString();
    consoleLog.innerHTML += `<div class="text-brand-400">[${timestamp}] Sync triggered manually. Rescanning opportunities...</div>`;
    consoleLog.scrollTop = consoleLog.scrollHeight;
  }
}

function openModal(title, message) {
  const overlay = document.getElementById('modalOverlay');
  const body = document.getElementById('modalBody');
  if (overlay && body) {
    body.innerHTML = `
      <h3 class="text-xl font-bold text-white mb-2">${title}</h3>
      <p class="text-xs text-gray-300 leading-relaxed mb-6">${message}</p>
      <button onclick="closeModal()" class="w-full bg-brand-500 hover:bg-brand-400 text-black font-bold text-xs py-2.5 rounded-xl transition">
        Dismiss
      </button>
    `;
    overlay.classList.remove('hidden');
  }
}

function closeModal() {
  const overlay = document.getElementById('modalOverlay');
  if (overlay) overlay.classList.add('hidden');
}