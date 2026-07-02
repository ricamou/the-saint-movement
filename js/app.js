
const CONFIG = window.SAINT_CONFIG;
const root = document.documentElement;
const savedTheme = localStorage.getItem("saint-theme");
if (savedTheme) root.setAttribute("data-theme", savedTheme);

window.addEventListener("load", () => {
  document.getElementById("loader")?.classList.add("hidden");
  createParticles();
  fetchDexData();
});

function copyContract() {
  navigator.clipboard.writeText(CONFIG.contract).then(() => showToast("CA copied")).catch(() => showToast(CONFIG.contract));
}
function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

document.getElementById("themeToggle")?.addEventListener("click", () => {
  const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
  root.setAttribute("data-theme", next);
  localStorage.setItem("saint-theme", next);
});
const navbar = document.getElementById("navbar");
window.addEventListener("scroll", () => navbar?.classList.toggle("scrolled", window.scrollY > 40));

const menuToggle = document.getElementById("menuToggle");
const mobileNav = document.getElementById("mobileNav");
menuToggle?.addEventListener("click", () => {
  mobileNav.classList.toggle("open");
  document.body.classList.toggle("menu-open");
});
mobileNav?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
  mobileNav.classList.remove("open");
  document.body.classList.remove("menu-open");
}));

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) entry.target.classList.add("visible");
  });
}, { threshold: 0.13 });
document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));

document.getElementById("refreshData")?.addEventListener("click", fetchDexData);

function formatUsd(value, compact = true) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  if (n < 0.01 && n > 0) return "$" + n.toPrecision(3);
  return new Intl.NumberFormat("en-US", { style:"currency", currency:"USD", notation: compact ? "compact" : "standard", maximumFractionDigits: n < 1 ? 6 : 2 }).format(n);
}
function formatNumber(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", { notation:"compact", maximumFractionDigits:2 }).format(n);
}
function setText(id, value) { document.querySelectorAll(`#${id}`).forEach((el) => el.textContent = value); }

async function fetchDexData() {
  const status = document.getElementById("dataStatus");
  if (!status || !CONFIG?.dexApi) return;
  status.textContent = "Loading live data…";
  try {
    const res = await fetch(CONFIG.dexApi, { cache: "no-store" });
    if (!res.ok) throw new Error("DexScreener API unavailable");
    const data = await res.json();
    const pairs = Array.isArray(data) ? data : (data.pairs || []);
    if (!pairs.length) throw new Error("No pair data found");
    const best = pairs.filter(p => p.chainId === "solana").sort((a,b) => Number(b?.liquidity?.usd || 0) - Number(a?.liquidity?.usd || 0))[0] || pairs[0];

    const buys = Number(best?.txns?.h24?.buys || 0);
    const sells = Number(best?.txns?.h24?.sells || 0);
    const change = Number(best?.priceChange?.h24);
    const liq = Number(best?.liquidity?.usd || 0);
    const vol = Number(best?.volume?.h24 || 0);
    const txns = buys + sells;

    setText("priceUsd", formatUsd(best?.priceUsd, false));
    setText("marketCap", formatUsd(best?.marketCap || best?.fdv));
    setText("liquidity", formatUsd(liq));
    setText("volume24h", formatUsd(vol));
    setText("txns24h", formatNumber(txns));
    setText("txnsSplit", `${formatNumber(buys)} buys / ${formatNumber(sells)} sells`);
    setText("priceChange", Number.isFinite(change) ? `24h ${change >= 0 ? "+" : ""}${change.toFixed(2)}%` : "24h —");

    const score = calculateHealthScore({ liq, vol, txns, change });
    setHealth(score);
    drawPulseChart([liq, vol, txns * 25, Math.abs(change || 0) * 1000, (best?.marketCap || best?.fdv || 0) / 20]);

    status.textContent = `Live data loaded · ${best.dexId || "DEX"}`;
  } catch (err) {
    status.textContent = "Live data unavailable — open DexScreener";
    setHealth(null);
    drawPulseChart([20,40,35,55,42,68,50]);
    console.warn(err);
  }
}
function calculateHealthScore({ liq, vol, txns, change }) {
  let score = 35;
  score += Math.min(liq / 1500, 25);
  score += Math.min(vol / 1500, 20);
  score += Math.min(txns / 8, 15);
  if (Number.isFinite(change)) score += Math.max(-10, Math.min(10, change / 2));
  return Math.max(0, Math.min(100, Math.round(score)));
}
function setHealth(score) {
  const ring = document.querySelector(".score-ring");
  const scoreEl = document.getElementById("healthScore");
  const label = document.getElementById("healthLabel");
  const desc = document.getElementById("healthDescription");
  if (!ring || !scoreEl) return;
  if (score === null) {
    scoreEl.textContent = "—";
    label && (label.textContent = "Waiting for data");
    desc && (desc.textContent = "Open DexScreener to verify live market data.");
    return;
  }
  scoreEl.textContent = score;
  ring.style.background = `conic-gradient(var(--gold) ${score * 3.6}deg, rgba(255,255,255,.12) 0deg)`;
  label && (label.textContent = score >= 75 ? "Strong signal" : score >= 50 ? "Developing signal" : "Early signal");
  desc && (desc.textContent = "Score based on liquidity, volume, transactions, and price activity.");
}
function drawPulseChart(values) {
  const canvas = document.getElementById("pulseChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0,0,w,h);
  const max = Math.max(...values, 1);
  const points = values.map((v,i) => ({
    x: 30 + i * ((w-60)/(values.length-1 || 1)),
    y: h - 30 - (v/max)*(h-60)
  }));
  ctx.strokeStyle = "rgba(230,195,106,.18)";
  ctx.lineWidth = 1;
  for (let y=30; y<h; y+=30){ ctx.beginPath(); ctx.moveTo(20,y); ctx.lineTo(w-20,y); ctx.stroke(); }
  const grad = ctx.createLinearGradient(0,0,w,0);
  grad.addColorStop(0,"#e6c36a"); grad.addColorStop(1,"#7cc7ff");
  ctx.strokeStyle = grad; ctx.lineWidth = 4; ctx.lineCap = "round";
  ctx.beginPath();
  points.forEach((p,i)=> i ? ctx.lineTo(p.x,p.y) : ctx.moveTo(p.x,p.y));
  ctx.stroke();
  points.forEach(p => { ctx.fillStyle = "#e6c36a"; ctx.beginPath(); ctx.arc(p.x,p.y,4,0,Math.PI*2); ctx.fill(); });
}
function createParticles() {
  const field = document.getElementById("particleField");
  if (!field) return;
  for (let i=0; i<46; i++) {
    const dot = document.createElement("i");
    dot.style.left = Math.random()*100 + "%";
    dot.style.top = Math.random()*100 + "%";
    dot.style.animationDuration = (6 + Math.random()*8) + "s";
    dot.style.animationDelay = (-Math.random()*8) + "s";
    field.appendChild(dot);
  }
}
