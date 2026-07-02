#!/usr/bin/env python3
"""
build_historico.py
Lê todos os HTMLs do repositório, extrai <script id="reuniao-meta">
e gera historico.html automaticamente.
"""
import json, re, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

REPO_ROOT = Path(__file__).parent
HISTORICO_OUT = REPO_ROOT / 'index.html'

def parse_date(s):
    for fmt in ('%d/%m/%Y',):
        try: return datetime.strptime(s, fmt)
        except: pass
    return datetime.min

def extract_meta(html_path):
    try:
        c = html_path.read_text(encoding='utf-8')
        # Use the LAST meta script (the one outside srcdoc)
        all_metas = re.findall(r'<script id="reuniao-meta" type="application/json">(.*?)</script>', c, re.DOTALL)
        m = type('m', (), {'group': lambda self, n: all_metas[-1]})() if all_metas else None
        if not m: return None
        return json.loads(m.group(1))
    except Exception as e:
        print(f"  Skip {html_path.name}: {e}", file=sys.stderr)
        return None

def fmt_brl(v):
    return 'R$\u00a0' + f'{int(v):,}'.replace(',', '.')

def obs_html(grupos):
    if not grupos:
        return '<p class="hobs-empty">Sem observações registradas.</p>'
    out = ''
    for g in grupos:
        items = ''.join(f'<li>{i}</li>' for i in g['items'])
        out += f'<div class="hobs-group"><span class="hobs-tag">{g["tag"]}</span><ul class="hobs-list">{items}</ul></div>'
    return out

# ── Collect ───────────────────────────────────────────────────────────────────
reunioes = []
for f in REPO_ROOT.glob('*.html'):
    if f.name in ('historico.html', 'index.html'): continue
    meta = extract_meta(f)
    if meta and meta.get('data'):
        slug = f.stem
        meta['url'] = f'https://mggastal.github.io/lindenberg-consolidado/{slug}'
        reunioes.append(meta)
        print(f"  ✓ {f.name} → {meta['data']}")

reunioes.sort(key=lambda r: parse_date(r['data']), reverse=True)
print(f"Total: {len(reunioes)} reuniões")

# ── Cards ─────────────────────────────────────────────────────────────────────
def make_card(r):
    n_obs = sum(len(g['items']) for g in r.get('obs_grupos', []))
    obs_label = f'Observações ({n_obs})' if n_obs else 'Sem observações'
    mes_ref = r.get('mes_ref', '')
    mes_badge = f'<span class="week-mes-badge">{mes_ref}</span>' if mes_ref else ''
    return f'''<div class="week-card">
  <div class="week-card-header">
    <div class="week-left">
      <div class="week-date">{r["data"]}</div>
      {mes_badge}
    </div>
    <a class="week-link-btn" href="{r["url"]}" target="_blank">Abrir →</a>
  </div>
  <div class="week-kpis">
    <div class="wkpi"><span class="wkpi-val">{r["facs"]:,}</span><span class="wkpi-label">FACs SIGAVI</span></div>
    <div class="wkpi"><span class="wkpi-val">{r["validas"]:,}</span><span class="wkpi-label">Válidas</span></div>
    <div class="wkpi"><span class="wkpi-val">{r["aprov"]}%</span><span class="wkpi-label">Atendimento</span></div>
    <div class="wkpi"><span class="wkpi-val">R$\u00a0{r["cpl"]}</span><span class="wkpi-label">CPL</span></div>
    <div class="wkpi"><span class="wkpi-val">{fmt_brl(r["invest"])}</span><span class="wkpi-label">Investido</span></div>
    <div class="wkpi"><span class="wkpi-val">{r["leads"]:,}</span><span class="wkpi-label">Leads Totais</span></div>
    <div class="wkpi"><span class="wkpi-val">{r["visitas"]}</span><span class="wkpi-label">Visitas</span></div>
  </div>
  <div class="week-obs-toggle" onclick="toggleWeekObs(this)">
    <span class="week-obs-label">{obs_label}</span>
    <span class="week-obs-arrow">▾</span>
  </div>
  <div class="week-obs-body" style="display:none;">{obs_html(r.get("obs_grupos",[]))}</div>
</div>'''

cards = '\n'.join(make_card(r) for r in reunioes) or '<p style="color:#999;text-align:center;padding:40px;">Nenhuma reunião encontrada.</p>'

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lindenberg — Histórico de Reuniões</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{
  --red:#C8102E; --red-muted:rgba(200,16,46,0.10);
  --off-white:#FAF8F7; --gray-light:#F0EDEC;
  --gray-dark:#7A6E6C; --text:#1A1210; --text-light:#5C4F4D;
  --border:rgba(200,16,46,0.12); --shadow:0 2px 16px rgba(26,18,16,0.07);
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'DM Sans',sans-serif;background:var(--off-white);color:var(--text);}}

header{{background:var(--red);padding:0 32px;}}
.header-inner{{max-width:960px;margin:0 auto;height:64px;display:flex;align-items:center;justify-content:space-between;}}
.brand{{display:flex;align-items:center;gap:12px;}}
.brand-logo{{width:34px;height:34px;background:white;border-radius:4px;display:flex;align-items:center;justify-content:center;}}
.brand-logo span{{font-family:'Playfair Display',serif;font-size:17px;font-weight:900;color:var(--red);}}
.brand-name{{font-family:'Playfair Display',serif;font-size:18px;font-weight:700;color:white;}}
.brand-sub{{font-size:11px;opacity:0.7;color:white;letter-spacing:0.06em;text-transform:uppercase;}}
.back-btn{{color:rgba(255,255,255,0.75);font-size:12px;text-decoration:none;border:1px solid rgba(255,255,255,0.3);padding:5px 12px;border-radius:6px;white-space:nowrap;}}
.back-btn:hover{{color:white;background:rgba(255,255,255,0.1);}}

main{{max-width:960px;margin:0 auto;padding:32px 32px 60px;}}
.page-title{{font-family:'Playfair Display',serif;font-size:26px;font-weight:700;margin-bottom:4px;}}
.page-sub{{font-size:12px;color:var(--gray-dark);margin-bottom:8px;}}
.last-updated{{font-size:11px;color:var(--gray-dark);margin-bottom:24px;}}

/* CARD */
.week-card{{background:white;border-radius:14px;box-shadow:var(--shadow);margin-bottom:16px;overflow:hidden;}}
.week-card-header{{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--border);gap:12px;}}
.week-left{{display:flex;align-items:center;gap:10px;}}
.week-date{{font-family:'Playfair Display',serif;font-size:18px;font-weight:700;white-space:nowrap;}}
.week-mes-badge{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--red);background:var(--red-muted);padding:3px 8px;border-radius:4px;white-space:nowrap;}}
.week-link-btn{{font-size:12px;font-weight:600;color:var(--red);text-decoration:none;border:1px solid var(--border);padding:5px 12px;border-radius:6px;white-space:nowrap;transition:all 0.15s;}}
.week-link-btn:hover{{background:var(--red);color:white;border-color:var(--red);}}

/* KPI ROW — single line, all on one row */
.week-kpis{{display:flex;flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;border-bottom:1px solid var(--gray-light);}}
.wkpi{{flex:1 1 0;min-width:90px;padding:12px 16px;border-right:1px solid var(--gray-light);display:flex;flex-direction:column;gap:2px;white-space:nowrap;}}
.wkpi:last-child{{border-right:none;}}
.wkpi-val{{font-size:15px;font-weight:700;color:var(--text);font-family:'Playfair Display',serif;}}
.wkpi-label{{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:var(--gray-dark);}}

/* OBS */
.week-obs-toggle{{display:flex;align-items:center;justify-content:space-between;padding:10px 20px;cursor:pointer;user-select:none;transition:background 0.15s;}}
.week-obs-toggle:hover{{background:var(--gray-light);}}
.week-obs-label{{font-size:11px;font-weight:600;color:var(--gray-dark);}}
.week-obs-arrow{{font-size:12px;color:var(--gray-dark);transition:transform 0.2s;}}
.week-obs-toggle.open .week-obs-arrow{{transform:rotate(180deg);}}
.week-obs-body{{padding:14px 20px 18px;border-top:1px solid var(--gray-light);display:flex;flex-direction:column;gap:12px;}}
.hobs-group{{}}
.hobs-tag{{display:inline-block;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--red);background:var(--red-muted);padding:2px 8px;border-radius:4px;margin-bottom:6px;}}
.hobs-list{{padding-left:16px;display:flex;flex-direction:column;gap:5px;}}
.hobs-list li{{font-size:13px;color:var(--text);line-height:1.5;}}
.hobs-empty{{font-size:12px;color:var(--gray-dark);font-style:italic;}}

footer{{text-align:center;padding:20px;font-size:11px;color:var(--gray-dark);}}

@media(max-width:600px){{
  main{{padding:16px 12px 40px;}} header{{padding:0 12px;}}
  .week-card-header{{flex-wrap:wrap;}} .brand-sub{{display:none;}}
}}
</style>
</head>
<body>
<header>
  <div class="header-inner">
    <div class="brand">
      <div class="brand-logo"><span>L</span></div>
      <div>
        <div class="brand-name">Lindenberg Consolidado</div>
        <div class="brand-sub">Histórico de Reuniões</div>
      </div>
    </div>
    <a class="back-btn" href="{reunioes[0]["url"] if reunioes else "#"}" target="_blank">← Dashboard atual</a>
  </div>
</header>
<main>
  <div class="page-title">Histórico de Reuniões</div>
  <p class="page-sub">{len(reunioes)} reuniões registradas · Números do mês em análise</p>
  <p class="last-updated">Atualizado automaticamente · {datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")}</p>
  {cards}
</main>
<footer>Dados exclusivos para uso no ambiente corporativo da Lindenberg. Desenvolvido por Grigoletti Mídias.</footer>
<script>
function toggleWeekObs(btn) {{
  btn.classList.toggle('open');
  var body = btn.nextElementSibling;
  body.style.display = body.style.display === 'none' ? 'flex' : 'none';
}}
</script>
</body>
</html>'''

HISTORICO_OUT.write_text(html, encoding='utf-8')
print(f"✓ {HISTORICO_OUT} gerado")
