import { useState, useEffect, useRef } from "react";

const CATEGORIES = [
  { id: "dev", label: "Dev", color: "#00e5cc", bg: "rgba(0,229,204,0.08)", glow: "rgba(0,229,204,0.15)" },
  { id: "trading", label: "Trading", color: "#ff9f43", bg: "rgba(255,159,67,0.08)", glow: "rgba(255,159,67,0.15)" },
  { id: "teaching", label: "Teaching", color: "#b088f9", bg: "rgba(176,136,249,0.08)", glow: "rgba(176,136,249,0.15)" },
  { id: "ideas", label: "Ideas", color: "#0be881", bg: "rgba(11,232,129,0.08)", glow: "rgba(11,232,129,0.15)" },
  { id: "personal", label: "Personal", color: "#fd79a8", bg: "rgba(253,121,168,0.08)", glow: "rgba(253,121,168,0.15)" },
  { id: "learning", label: "Learning", color: "#74b9ff", bg: "rgba(116,185,255,0.08)", glow: "rgba(116,185,255,0.15)" },
];

const STATUS = [
  { id: "active", label: "Active", color: "#00e5cc", icon: "▶" },
  { id: "paused", label: "Paused", color: "#fdcb6e", icon: "⏸" },
  { id: "backlog", label: "Backlog", color: "#636e72", icon: "◻" },
  { id: "done", label: "Done", color: "#0be881", icon: "✓" },
];

const PRIORITY = [
  { id: "p0", label: "P0", color: "#ff6b6b" },
  { id: "p1", label: "P1", color: "#ff9f43" },
  { id: "p2", label: "P2", color: "#fdcb6e" },
  { id: "p3", label: "P3", color: "#636e72" },
];

const SOURCE_META = {
  disk: { icon: "⬡", label: "disk", color: "#00e5cc" },
  obsidian: { icon: "◈", label: "obsidian", color: "#b088f9" },
  manual: { icon: "✎", label: "manual", color: "#0be881" },
};

const MOCK_ITEMS = [
  { id: "d1", title: "Stark", subtitle: "Trading Intelligence System", category: "dev", status: "active", priority: "p0", source: "disk", path: "D:/Projects/stark", type: "tauri", notes: "Automate binary scoring system. Reduce nightly prep from ~2-3 hours to under 10 minutes. Tauri + React + SQLite.", focused: true, lastModified: "2 hours ago" },
  { id: "d2", title: "IdeaEngine", subtitle: "Business Idea Discovery", category: "dev", status: "active", priority: "p1", source: "disk", path: "D:/Projects/ideaengine", type: "python", notes: "Claude Code native architecture. Mines Reddit, G2/Capterra for pain points. Validates demand and scores opportunities.", focused: true, lastModified: "5 hours ago" },
  { id: "o1", title: "Angular Teaching Plan", subtitle: "12-Week Structured Curriculum", category: "teaching", status: "active", priority: "p1", source: "obsidian", path: "Dashboard/angular-teaching-plan.md", type: "obsidian-folder", notes: "Phase 1: Foundations, Phase 2: Build Something Real, Phase 3: Polish & Level Up. Designer-friendly analogies mapping Angular to Figma.", focused: true, lastModified: "1 day ago" },
  { id: "o2", title: "Paid Signal Subscription", subtitle: "Monetize Stark's daily focus list", category: "ideas", status: "backlog", priority: "p2", source: "obsidian", path: "Ideas/paid-signals.md", type: "obsidian-tag", notes: "Build subscription product on top of Stark's scoring output. Target: recurring passive income from trading expertise.", focused: false, lastModified: "3 days ago" },
  { id: "d3", title: "Can You Run It for LLMs", subtitle: "Hardware compatibility checker", category: "dev", status: "paused", priority: "p2", source: "disk", path: "D:/Projects/llm-checker", type: "rust", notes: "Rust/Tauri native detection agent, model database, three-tier monetization. PRD and design spec complete.", focused: false, lastModified: "1 week ago" },
  { id: "o3", title: "WhatsApp AI Receptionist", subtitle: "Indian market SaaS", category: "ideas", status: "backlog", priority: "p3", source: "obsidian", path: "Ideas/whatsapp-ai.md", type: "obsidian-tag", notes: "WhatsApp Business API + LLM agent for SMB appointment booking and lead qualification. Indian market focus.", focused: false, lastModified: "2 weeks ago" },
  { id: "m1", title: "Portfolio Risk Review", subtitle: "Weekly GTT and position check", category: "trading", status: "active", priority: "p1", source: "manual", notes: "Review all open positions, verify GTT stop-losses are in place, check position sizing against current capital.", focused: false, lastModified: "Today" },
  { id: "o4", title: "Regional Content Engine", subtitle: "Multi-language content repurposing", category: "ideas", status: "backlog", priority: "p3", source: "obsidian", path: "Ideas/regional-content.md", type: "obsidian-frontmatter", notes: "LLM-powered content repurposing for regional Indian languages. Target vernacular markets.", focused: false, lastModified: "3 weeks ago" },
  { id: "d4", title: "dotfiles", subtitle: "System configuration", category: "personal", status: "active", priority: "p3", source: "disk", path: "D:/Projects/dotfiles", type: "git", notes: "WSL + Windows terminal configs, VS Code settings, shell aliases.", focused: false, lastModified: "4 days ago" },
  { id: "m2", title: "Explore Cursor AI", subtitle: "Evaluate for daily dev workflow", category: "learning", status: "backlog", priority: "p2", source: "manual", notes: "Compare with Claude Code CLI for coding tasks. Test on Stark codebase.", focused: false, lastModified: "Yesterday" },
];

const getCat = (id) => CATEGORIES.find(c => c.id === id) || CATEGORIES[0];
const getStat = (id) => STATUS.find(s => s.id === id) || STATUS[2];
const getPri = (id) => PRIORITY.find(p => p.id === id) || PRIORITY[2];

export default function CMDCenter() {
  const [items, setItems] = useState(MOCK_ITEMS);
  const [view, setView] = useState("board");
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [quickText, setQuickText] = useState("");
  const [quickCat, setQuickCat] = useState("dev");
  const [toast, setToast] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [form, setForm] = useState({ title: "", category: "dev", status: "backlog", priority: "p2", notes: "", focused: false });
  const inputRef = useRef(null);

  useEffect(() => { setTimeout(() => setMounted(true), 100); }, []);

  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2000); };

  const doSync = () => {
    setSyncing(true);
    setTimeout(() => { setSyncing(false); flash("Synced — 4 disk · 4 obsidian · 2 manual"); }, 1200);
  };

  const toggleFocus = (id) => setItems(prev => prev.map(i => i.id === id ? { ...i, focused: !i.focused } : i));
  const cycleStatus = (id) => {
    const order = ["backlog", "active", "paused", "done"];
    setItems(prev => prev.map(i => {
      if (i.id !== id) return i;
      return { ...i, status: order[(order.indexOf(i.status) + 1) % order.length] };
    }));
  };
  const deleteItem = (id) => { setItems(prev => prev.filter(i => i.id !== id)); setExpanded(null); setShowModal(false); flash("Removed"); };

  const quickAdd = () => {
    if (!quickText.trim()) return;
    const nw = { id: `m${Date.now()}`, title: quickText.trim(), category: quickCat, status: "backlog", priority: "p2", source: "manual", notes: "", focused: false, lastModified: "Just now" };
    setItems(prev => [nw, ...prev]);
    setQuickText("");
    flash("Added to backlog");
  };

  const openAdd = () => {
    setForm({ title: "", category: "dev", status: "backlog", priority: "p2", notes: "", focused: false });
    setEditItem(null); setShowModal(true);
  };
  const openEdit = (item) => {
    setForm({ title: item.title, category: item.category, status: item.status, priority: item.priority, notes: item.notes || "", focused: item.focused });
    setEditItem(item); setShowModal(true);
  };
  const saveItem = () => {
    if (!form.title.trim()) return;
    if (editItem) {
      setItems(prev => prev.map(i => i.id === editItem.id ? { ...i, ...form } : i));
      flash("Updated");
    } else {
      setItems(prev => [{ id: `m${Date.now()}`, ...form, source: "manual", lastModified: "Just now" }, ...prev]);
      flash("Added");
    }
    setShowModal(false);
  };

  const filtered = filter === "all" ? items : items.filter(i => i.category === filter);
  const focusedItems = items.filter(i => i.focused && i.status !== "done");
  const doneItems = items.filter(i => i.status === "done");
  const stats = {
    active: items.filter(i => i.status === "active").length,
    backlog: items.filter(i => i.status === "backlog").length,
    done: doneItems.length,
    focused: focusedItems.length,
    disk: items.filter(i => i.source === "disk").length,
    obsidian: items.filter(i => i.source === "obsidian").length,
    manual: items.filter(i => i.source === "manual").length,
  };

  return (
    <div style={S.root}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap');
        @keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
        @keyframes slideUp { from { opacity:0; transform:translateY(30px); } to { opacity:1; transform:translateY(0); } }
        @keyframes spin { to { transform:rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:0.4; } 50% { opacity:1; } }
        @keyframes gridPan { from { background-position: 0 0; } to { background-position: 40px 40px; } }
        @keyframes glowPulse { 0%,100% { box-shadow: 0 0 0 rgba(0,229,204,0); } 50% { box-shadow: 0 0 20px rgba(0,229,204,0.1); } }
        .card-enter { animation: fadeUp 0.3s ease both; }
        .sync-spin { animation: spin 0.8s linear infinite; }
        .grid-bg {
          background-image: 
            linear-gradient(rgba(0,229,204,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,229,204,0.03) 1px, transparent 1px);
          background-size: 40px 40px;
          animation: gridPan 20s linear infinite;
        }
        *::-webkit-scrollbar { width: 5px; }
        *::-webkit-scrollbar-track { background: transparent; }
        *::-webkit-scrollbar-thumb { background: #1a2332; border-radius: 3px; }
      `}</style>

      {/* Ambient grid background */}
      <div className="grid-bg" style={S.gridOverlay} />

      {/* Toast */}
      {toast && <div style={S.toast}><span style={S.toastDot} />{toast}</div>}

      {/* ═══ HEADER ═══ */}
      <header style={{ ...S.header, opacity: mounted ? 1 : 0, transform: mounted ? "none" : "translateY(-8px)", transition: "all 0.5s ease" }}>
        <div style={S.headerLeft}>
          <div style={S.logoRow}>
            <div style={S.logoMark}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L22 12L12 22L2 12Z" stroke="#00e5cc" strokeWidth="1.5" fill="rgba(0,229,204,0.1)" />
                <path d="M12 7L17 12L12 17L7 12Z" fill="#00e5cc" opacity="0.6" />
              </svg>
            </div>
            <span style={S.logoText}>CMD CENTER</span>
            <span style={S.logoDivider} />
            <span style={S.logoVersion}>v1.0</span>
          </div>
          <div style={S.statsRow}>
            <StatPill label="active" value={stats.active} color="#00e5cc" />
            <StatPill label="backlog" value={stats.backlog} color="#636e72" />
            <StatPill label="done" value={stats.done} color="#0be881" />
            <StatPill label="focus" value={stats.focused} color="#fdcb6e" />
          </div>
        </div>
        <div style={S.headerRight}>
          <div style={S.sourcePills}>
            {[["disk", stats.disk], ["obsidian", stats.obsidian], ["manual", stats.manual]].map(([src, n]) => (
              <span key={src} style={{ ...S.sourcePill, color: SOURCE_META[src].color, borderColor: `${SOURCE_META[src].color}33` }}>
                {SOURCE_META[src].icon} {n} {src}
              </span>
            ))}
          </div>
          <button style={S.syncBtn} onClick={doSync} title="Sync now">
            <span className={syncing ? "sync-spin" : ""} style={{ display: "inline-block" }}>⟳</span>
          </button>
        </div>
      </header>

      {/* ═══ QUICK ADD ═══ */}
      <div style={{ ...S.quickWrap, opacity: mounted ? 1 : 0, transition: "opacity 0.5s ease 0.1s" }}>
        <div style={S.quickBar}>
          <span style={S.quickIcon}>⌘</span>
          <select style={S.quickSelect} value={quickCat} onChange={e => setQuickCat(e.target.value)}>
            {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
          <input
            ref={inputRef}
            style={S.quickInput}
            value={quickText}
            onChange={e => setQuickText(e.target.value)}
            onKeyDown={e => e.key === "Enter" && quickAdd()}
            placeholder="Quick capture — type anything, hit Enter..."
          />
          <button style={{ ...S.quickBtn, opacity: quickText.trim() ? 1 : 0.3 }} onClick={quickAdd}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      </div>

      {/* ═══ NAV ═══ */}
      <div style={{ ...S.nav, opacity: mounted ? 1 : 0, transition: "opacity 0.5s ease 0.15s" }}>
        <div style={S.viewTabs}>
          {[["board", "⊞ Board"], ["list", "≡ List"], ["focus", `★ Focus`]].map(([k, l]) => (
            <button key={k} onClick={() => { setView(k); setExpanded(null); }}
              style={view === k ? { ...S.tab, ...S.tabActive } : S.tab}>
              {l}{k === "focus" && focusedItems.length > 0 ? ` (${focusedItems.length})` : ""}
            </button>
          ))}
        </div>
        <div style={S.filters}>
          <button style={filter === "all" ? { ...S.filterChip, ...S.filterActive } : S.filterChip} onClick={() => setFilter("all")}>All</button>
          {CATEGORIES.map(c => (
            <button key={c.id}
              style={filter === c.id ? { ...S.filterChip, background: c.bg, color: c.color, borderColor: `${c.color}44` } : S.filterChip}
              onClick={() => setFilter(c.id)}>
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* ═══ CONTENT ═══ */}
      <div style={S.content}>
        {/* BOARD VIEW */}
        {view === "board" && (
          <div style={S.board}>
            {STATUS.filter(s => s.id !== "done").map(status => {
              const col = filtered.filter(i => i.status === status.id).sort((a, b) =>
                PRIORITY.findIndex(p => p.id === a.priority) - PRIORITY.findIndex(p => p.id === b.priority)
              );
              return (
                <div key={status.id} style={S.column}>
                  <div style={S.colHead}>
                    <span style={{ ...S.colDot, background: status.color, boxShadow: `0 0 8px ${status.color}44` }} />
                    <span style={S.colLabel}>{status.label}</span>
                    <span style={S.colCount}>{col.length}</span>
                  </div>
                  <div style={S.colBody}>
                    {col.length === 0 && <p style={S.colEmpty}>No items</p>}
                    {col.map((item, idx) => (
                      <Card key={item.id} item={item} compact
                        delay={idx * 0.05}
                        isExpanded={expanded === item.id}
                        onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                        onFocus={() => toggleFocus(item.id)}
                        onCycle={() => cycleStatus(item.id)}
                        onEdit={() => openEdit(item)}
                        onDelete={() => deleteItem(item.id)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* LIST VIEW */}
        {view === "list" && (
          <div style={S.list}>
            {filtered.length === 0 && <p style={S.emptyState}>No items found.</p>}
            {[...filtered].sort((a, b) => {
              const so = ["active", "paused", "backlog", "done"];
              const po = ["p0", "p1", "p2", "p3"];
              if (so.indexOf(a.status) !== so.indexOf(b.status)) return so.indexOf(a.status) - so.indexOf(b.status);
              return po.indexOf(a.priority) - po.indexOf(b.priority);
            }).map((item, idx) => (
              <Card key={item.id} item={item} delay={idx * 0.04}
                isExpanded={expanded === item.id}
                onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                onFocus={() => toggleFocus(item.id)}
                onCycle={() => cycleStatus(item.id)}
                onEdit={() => openEdit(item)}
                onDelete={() => deleteItem(item.id)}
              />
            ))}
          </div>
        )}

        {/* FOCUS VIEW */}
        {view === "focus" && (
          <div>
            <p style={S.hint}>Items pinned for today's focus. Star any card to add it here.</p>
            {focusedItems.length === 0 && <p style={S.emptyState}>No items in focus. Tap ★ on any card.</p>}
            <div style={S.focusGrid}>
              {focusedItems.map((item, idx) => (
                <Card key={item.id} item={item} delay={idx * 0.06}
                  isExpanded={expanded === item.id}
                  onToggle={() => setExpanded(expanded === item.id ? null : item.id)}
                  onFocus={() => toggleFocus(item.id)}
                  onCycle={() => cycleStatus(item.id)}
                  onEdit={() => openEdit(item)}
                  onDelete={() => deleteItem(item.id)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Done section */}
      {view !== "focus" && doneItems.length > 0 && (
        <div style={S.doneWrap}>
          <details>
            <summary style={S.doneSummary}>▸ Completed ({doneItems.length})</summary>
            <div style={S.doneList}>
              {doneItems.map(i => (
                <div key={i.id} style={S.doneItem}>
                  <span style={S.doneTitle}>{i.title}</span>
                  <button style={S.doneX} onClick={() => deleteItem(i.id)}>×</button>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* FAB */}
      <button style={S.fab} onClick={openAdd}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>New Item</span>
      </button>

      {/* ═══ MODAL ═══ */}
      {showModal && (
        <div style={S.overlay} onClick={() => setShowModal(false)}>
          <div style={S.modal} onClick={e => e.stopPropagation()}>
            <div style={S.modalHeader}>
              <h3 style={S.modalTitle}>{editItem ? "Edit Item" : "New Item"}</h3>
              <button style={S.modalClose} onClick={() => setShowModal(false)}>×</button>
            </div>
            <input style={S.modalInput} placeholder="Title" value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))} autoFocus />
            <textarea style={S.modalTextarea} placeholder="Notes (optional)" rows={3}
              value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
            <div style={S.modalRow}>
              <label style={S.modalLabel}>Category</label>
              <div style={S.chipRow}>
                {CATEGORIES.map(c => (
                  <button key={c.id} onClick={() => setForm(f => ({ ...f, category: c.id }))}
                    style={form.category === c.id ? { ...S.chip, background: c.bg, color: c.color, borderColor: `${c.color}55` } : S.chip}>
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
            <div style={S.modalRow}>
              <label style={S.modalLabel}>Status</label>
              <div style={S.chipRow}>
                {STATUS.map(s => (
                  <button key={s.id} onClick={() => setForm(f => ({ ...f, status: s.id }))}
                    style={form.status === s.id ? { ...S.chip, background: `${s.color}18`, color: s.color, borderColor: `${s.color}55` } : S.chip}>
                    {s.icon} {s.label}
                  </button>
                ))}
              </div>
            </div>
            <div style={S.modalRow}>
              <label style={S.modalLabel}>Priority</label>
              <div style={S.chipRow}>
                {PRIORITY.map(p => (
                  <button key={p.id} onClick={() => setForm(f => ({ ...f, priority: p.id }))}
                    style={form.priority === p.id ? { ...S.chip, background: `${p.color}18`, color: p.color, borderColor: `${p.color}55` } : S.chip}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div style={S.modalRow}>
              <button style={S.focusToggle} onClick={() => setForm(f => ({ ...f, focused: !f.focused }))}>
                <span style={{ color: form.focused ? "#fdcb6e" : "#3d4f5f", fontSize: 18 }}>{form.focused ? "★" : "☆"}</span>
                <span style={S.modalLabel}>Daily Focus</span>
              </button>
            </div>
            <div style={S.modalActions}>
              {editItem && <button style={S.btnDanger} onClick={() => deleteItem(editItem.id)}>Delete</button>}
              <div style={{ flex: 1 }} />
              <button style={S.btnGhost} onClick={() => setShowModal(false)}>Cancel</button>
              <button style={{ ...S.btnPrimary, opacity: form.title.trim() ? 1 : 0.4 }} onClick={saveItem}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatPill({ label, value, color }) {
  return (
    <span style={S.statPill}>
      <span style={{ color, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace" }}>{value}</span>
      <span style={{ color: "#4a5c6b" }}>{label}</span>
    </span>
  );
}

function Card({ item, compact, delay = 0, isExpanded, onToggle, onFocus, onCycle, onEdit, onDelete }) {
  const cat = getCat(item.category);
  const status = getStat(item.status);
  const pri = getPri(item.priority);
  const src = SOURCE_META[item.source] || SOURCE_META.manual;

  return (
    <div className="card-enter" onClick={onToggle}
      style={{
        ...S.card,
        ...(compact ? S.cardCompact : {}),
        borderLeftColor: cat.color,
        animationDelay: `${delay}s`,
      }}>
      <div style={S.cardTop}>
        <button style={{ ...S.star, color: item.focused ? "#fdcb6e" : "#2a3a4a" }}
          onClick={e => { e.stopPropagation(); onFocus(); }}>
          {item.focused ? "★" : "☆"}
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={S.cardTitleRow}>
            <span style={S.cardTitle}>{item.title}</span>
            {item.subtitle && <span style={S.cardSubtitle}>{item.subtitle}</span>}
          </div>
        </div>
      </div>
      <div style={S.cardMeta}>
        <span style={{ ...S.badge, background: cat.bg, color: cat.color }}>{cat.label}</span>
        <span style={{ ...S.badge, background: `${pri.color}14`, color: pri.color, fontWeight: 600 }}>{pri.label}</span>
        <button style={{ ...S.statusBadge, background: `${status.color}18`, color: status.color }}
          onClick={e => { e.stopPropagation(); onCycle(); }} title="Cycle status">
          {status.icon} {status.label}
        </button>
        {item.type && <span style={S.typeBadge}>{item.type}</span>}
        <span style={{ ...S.srcBadge, color: src.color }}>{src.icon} {src.label}</span>
      </div>

      {isExpanded && (
        <div style={S.expandedArea} onClick={e => e.stopPropagation()}>
          {item.notes && <p style={S.notes}>{item.notes}</p>}
          {item.path && <p style={S.pathText}>{item.path}</p>}
          {item.lastModified && <p style={S.timeText}>Last modified: {item.lastModified}</p>}
          <div style={S.cardActions}>
            <button style={S.actionBtn} onClick={onEdit}>Edit</button>
            <button style={{ ...S.actionBtn, ...S.actionDanger }} onClick={onDelete}>Delete</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   STYLES
   ═══════════════════════════════════════════════════════════ */
const S = {
  root: {
    minHeight: "100vh", background: "#080d14", color: "#c8d6df",
    fontFamily: "'Outfit', sans-serif", position: "relative", overflow: "hidden",
  },
  gridOverlay: {
    position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
  },

  // Toast
  toast: {
    position: "fixed", top: 16, left: "50%", transform: "translateX(-50%)", zIndex: 999,
    background: "#0f1923", border: "1px solid #00e5cc33", borderRadius: 8, padding: "8px 20px",
    fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: "#00e5cc",
    display: "flex", alignItems: "center", gap: 8,
    boxShadow: "0 8px 32px rgba(0,0,0,0.5)", animation: "fadeUp 0.2s ease",
  },
  toastDot: { width: 6, height: 6, borderRadius: "50%", background: "#00e5cc", animation: "pulse 1s infinite" },

  // Header
  header: {
    display: "flex", justifyContent: "space-between", alignItems: "flex-start",
    padding: "16px 24px", borderBottom: "1px solid #111d2a", position: "relative", zIndex: 10,
    flexWrap: "wrap", gap: 12,
  },
  headerLeft: { display: "flex", flexDirection: "column", gap: 8 },
  headerRight: { display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" },
  logoRow: { display: "flex", alignItems: "center", gap: 10 },
  logoMark: { display: "flex" },
  logoText: { fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, fontSize: 15, letterSpacing: 3, color: "#e8eff4" },
  logoDivider: { width: 1, height: 16, background: "#1a2a3a" },
  logoVersion: { fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, color: "#3d4f5f", letterSpacing: 1 },
  statsRow: { display: "flex", gap: 12, flexWrap: "wrap" },
  statPill: { display: "flex", gap: 5, fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" },
  sourcePills: { display: "flex", gap: 6 },
  sourcePill: {
    fontFamily: "'IBM Plex Mono', monospace", fontSize: 10, padding: "3px 8px",
    borderRadius: 10, border: "1px solid", letterSpacing: 0.5,
  },
  syncBtn: {
    background: "transparent", border: "1px solid #1a2a3a", color: "#4a5c6b",
    borderRadius: 8, width: 36, height: 36, fontSize: 17, cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s",
  },

  // Quick Add
  quickWrap: { padding: "12px 24px", borderBottom: "1px solid #111d2a", position: "relative", zIndex: 10 },
  quickBar: {
    display: "flex", gap: 8, alignItems: "center", background: "#0c1520",
    borderRadius: 12, padding: "5px 6px 5px 14px", border: "1px solid #16202e",
    transition: "border-color 0.2s",
  },
  quickIcon: { color: "#2a3a4a", fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, fontWeight: 600 },
  quickSelect: {
    background: "transparent", border: "none", color: "#4a5c6b", fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11, outline: "none", cursor: "pointer",
  },
  quickInput: {
    flex: 1, background: "transparent", border: "none", color: "#c8d6df", fontSize: 14,
    outline: "none", fontFamily: "'Outfit', sans-serif", padding: "8px 0", minWidth: 0,
  },
  quickBtn: {
    background: "#00e5cc", color: "#080d14", border: "none", borderRadius: 8,
    width: 36, height: 36, cursor: "pointer", display: "flex", alignItems: "center",
    justifyContent: "center", flexShrink: 0, transition: "all 0.15s",
  },

  // Nav
  nav: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "12px 24px", gap: 12, flexWrap: "wrap", position: "relative", zIndex: 10,
  },
  viewTabs: { display: "flex", gap: 4 },
  tab: {
    background: "transparent", border: "1px solid #16202e", color: "#4a5c6b",
    borderRadius: 8, padding: "7px 16px", fontSize: 12, fontFamily: "'IBM Plex Mono', monospace",
    cursor: "pointer", transition: "all 0.15s", letterSpacing: 0.5,
  },
  tabActive: { background: "rgba(0,229,204,0.06)", color: "#00e5cc", borderColor: "#00e5cc33" },
  filters: { display: "flex", gap: 4, flexWrap: "wrap" },
  filterChip: {
    background: "transparent", border: "1px solid #16202e", color: "#4a5c6b",
    borderRadius: 20, padding: "4px 12px", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace",
    cursor: "pointer", transition: "all 0.15s",
  },
  filterActive: { background: "rgba(0,229,204,0.06)", color: "#00e5cc", borderColor: "#00e5cc33" },

  // Content
  content: { padding: "0 24px 100px", position: "relative", zIndex: 10 },
  hint: { color: "#3d4f5f", fontSize: 12, marginBottom: 14, fontFamily: "'IBM Plex Mono', monospace" },
  emptyState: {
    color: "#2a3a4a", textAlign: "center", padding: "60px 20px",
    fontFamily: "'IBM Plex Mono', monospace", fontSize: 13,
  },

  // Board
  board: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 },
  column: {
    background: "#0a1018", borderRadius: 12, padding: 14, minHeight: 140,
    border: "1px solid #111d2a",
  },
  colHead: {
    display: "flex", alignItems: "center", gap: 8, marginBottom: 12,
    paddingBottom: 10, borderBottom: "1px solid #111d2a",
  },
  colDot: { width: 8, height: 8, borderRadius: "50%" },
  colLabel: { fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, fontWeight: 600, color: "#6b7f8e", textTransform: "uppercase", letterSpacing: 1.5 },
  colCount: { marginLeft: "auto", fontSize: 11, color: "#2a3a4a", fontFamily: "'IBM Plex Mono', monospace" },
  colBody: { display: "flex", flexDirection: "column", gap: 8 },
  colEmpty: { color: "#1a2a3a", fontSize: 12, textAlign: "center", padding: 28, fontFamily: "'IBM Plex Mono', monospace" },

  // List / Focus
  list: { display: "flex", flexDirection: "column", gap: 8 },
  focusGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 10 },

  // Card
  card: {
    background: "#0c1520", borderRadius: 10, padding: "13px 15px", cursor: "pointer",
    border: "1px solid #16202e", borderLeft: "3px solid #00e5cc",
    transition: "border-color 0.15s, box-shadow 0.2s",
  },
  cardCompact: { padding: "11px 13px" },
  cardTop: { display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 8 },
  star: {
    background: "none", border: "none", fontSize: 16, cursor: "pointer", padding: 0,
    lineHeight: 1, flexShrink: 0, marginTop: 2, transition: "color 0.15s",
  },
  cardTitleRow: { display: "flex", flexDirection: "column", gap: 2, minWidth: 0 },
  cardTitle: { fontSize: 13, fontWeight: 600, color: "#e0eaf0", lineHeight: 1.35 },
  cardSubtitle: { fontSize: 11, color: "#4a5c6b", fontFamily: "'IBM Plex Mono', monospace" },
  cardMeta: { display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" },
  badge: {
    fontSize: 10, padding: "2px 8px", borderRadius: 20, fontFamily: "'IBM Plex Mono', monospace",
    letterSpacing: 0.5, lineHeight: "16px",
  },
  statusBadge: {
    fontSize: 10, padding: "2px 8px", borderRadius: 20, fontFamily: "'IBM Plex Mono', monospace",
    border: "none", cursor: "pointer", letterSpacing: 0.5, lineHeight: "16px",
  },
  typeBadge: {
    fontSize: 9, padding: "2px 6px", borderRadius: 8, fontFamily: "'IBM Plex Mono', monospace",
    color: "#3d4f5f", border: "1px solid #16202e", letterSpacing: 0.5,
  },
  srcBadge: {
    fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", marginLeft: "auto",
    letterSpacing: 0.5, opacity: 0.7,
  },

  // Expanded
  expandedArea: {
    marginTop: 10, paddingTop: 10, borderTop: "1px solid #111d2a",
    animation: "fadeUp 0.15s ease",
  },
  notes: { fontSize: 12, color: "#6b7f8e", lineHeight: 1.6, marginBottom: 8, fontFamily: "'IBM Plex Mono', monospace" },
  pathText: { fontSize: 10, color: "#2a3a4a", fontFamily: "'IBM Plex Mono', monospace", marginBottom: 4, wordBreak: "break-all" },
  timeText: { fontSize: 10, color: "#2a3a4a", fontFamily: "'IBM Plex Mono', monospace", marginBottom: 10 },
  cardActions: { display: "flex", gap: 8 },
  actionBtn: {
    background: "#0f1923", border: "1px solid #16202e", color: "#4a5c6b",
    borderRadius: 6, padding: "5px 14px", fontSize: 11, cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace", transition: "all 0.15s",
  },
  actionDanger: { borderColor: "#ff6b6b22", color: "#ff6b6b" },

  // Done
  doneWrap: {
    margin: "16px 24px 0", borderRadius: 10, border: "1px solid #111d2a",
    background: "#0a1018", position: "relative", zIndex: 10,
  },
  doneSummary: {
    padding: "10px 14px", cursor: "pointer", fontSize: 12, color: "#3d4f5f",
    fontFamily: "'IBM Plex Mono', monospace", listStyle: "none",
  },
  doneList: { padding: "0 14px 14px" },
  doneItem: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "5px 0", borderBottom: "1px solid #111d2a33",
  },
  doneTitle: { fontSize: 12, color: "#2a3a4a", textDecoration: "line-through" },
  doneX: { background: "none", border: "none", color: "#2a3a4a", fontSize: 14, cursor: "pointer" },

  // FAB
  fab: {
    position: "fixed", bottom: 24, right: 24, background: "#00e5cc", color: "#080d14",
    border: "none", borderRadius: 12, padding: "12px 20px", fontWeight: 700, fontSize: 13,
    cursor: "pointer", fontFamily: "'IBM Plex Mono', monospace",
    boxShadow: "0 4px 24px rgba(0,229,204,0.25), 0 0 40px rgba(0,229,204,0.1)",
    zIndex: 40, display: "flex", alignItems: "center", gap: 8,
    transition: "transform 0.1s",
  },

  // Modal
  overlay: {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex",
    alignItems: "flex-end", justifyContent: "center", zIndex: 100,
    animation: "fadeUp 0.15s ease",
  },
  modal: {
    background: "#0c1520", borderRadius: "16px 16px 0 0", padding: "24px 22px 32px",
    width: "100%", maxWidth: 540, maxHeight: "88vh", overflowY: "auto",
    border: "1px solid #16202e", animation: "slideUp 0.25s ease",
  },
  modalHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 },
  modalTitle: { fontSize: 16, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace", color: "#e0eaf0", margin: 0 },
  modalClose: {
    background: "none", border: "none", color: "#3d4f5f", fontSize: 22, cursor: "pointer",
    width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center",
  },
  modalInput: {
    width: "100%", background: "#080d14", border: "1px solid #16202e", borderRadius: 8,
    padding: "11px 14px", color: "#e0eaf0", fontSize: 14, marginBottom: 10, outline: "none",
    fontFamily: "'Outfit', sans-serif", boxSizing: "border-box", transition: "border-color 0.15s",
  },
  modalTextarea: {
    width: "100%", background: "#080d14", border: "1px solid #16202e", borderRadius: 8,
    padding: "11px 14px", color: "#c8d6df", fontSize: 12, marginBottom: 14, outline: "none",
    fontFamily: "'IBM Plex Mono', monospace", resize: "vertical", boxSizing: "border-box",
  },
  modalRow: { marginBottom: 14 },
  modalLabel: {
    fontSize: 10, color: "#3d4f5f", fontFamily: "'IBM Plex Mono', monospace",
    textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 6, display: "block",
  },
  chipRow: { display: "flex", gap: 6, flexWrap: "wrap" },
  chip: {
    background: "transparent", border: "1px solid #16202e", color: "#4a5c6b",
    borderRadius: 20, padding: "5px 13px", fontSize: 11, cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace", transition: "all 0.15s",
  },
  focusToggle: {
    background: "none", border: "none", cursor: "pointer", display: "flex",
    alignItems: "center", gap: 8, padding: 0,
  },
  modalActions: { display: "flex", gap: 8, marginTop: 22, alignItems: "center" },
  btnGhost: {
    background: "transparent", border: "1px solid #16202e", color: "#4a5c6b",
    borderRadius: 8, padding: "9px 18px", fontSize: 13, cursor: "pointer",
  },
  btnPrimary: {
    background: "#00e5cc", color: "#080d14", border: "none", borderRadius: 8,
    padding: "9px 22px", fontSize: 13, fontWeight: 700, cursor: "pointer",
    fontFamily: "'IBM Plex Mono', monospace",
  },
  btnDanger: {
    background: "transparent", border: "1px solid #ff6b6b33", color: "#ff6b6b",
    borderRadius: 8, padding: "9px 16px", fontSize: 13, cursor: "pointer",
  },
};
