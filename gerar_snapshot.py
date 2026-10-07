#!/usr/bin/env python3
"""
gerar_snapshot.py — gera o HTML semanal do Revenue Board a partir do Histórico (Google Sheets público).

Uso:
  python gerar_snapshot.py --data 08/10/2026 --mes-ref Outubro --dia 7 --budget-meta 470000
  python gerar_snapshot.py --data 08/10/2026 --mes-ref Outubro --dia 7 --budget-meta 470000 --csv hist.csv   # offline

Parte do HTML mais recente do repositório (template) e substitui apenas:
  const DATA (produto x mês), const D (aba Reunião), #reuniao-meta, reportDate/obsDate.
Não mexe em JS/CSS. O push dispara o workflow que regenera o index.html.
"""
import argparse, csv, io, json, re, subprocess, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SHEET_ID = "15HsjCSKf0gBTsz73jKQg-kuqPg9c7FSsJ2u39mSqklY"   # Revenue Board (aba Histórico = 1ª)
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
ROOT = Path(__file__).parent
MES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
ABR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']


def num(s):
    s = (s or '').strip().replace('R$', '').replace('%', '').replace('\xa0', '').strip()
    if not s or s in ('-', '—'):
        return None
    try:
        return float(s.replace('.', '').replace(',', '.'))
    except ValueError:
        return None


def load_hist(csv_text):
    rows = list(csv.reader(io.StringIO(csv_text)))
    hdr = rows[1]
    ix = {}
    for i, h in enumerate(hdr):
        if h and h not in ix:
            ix[h] = i
    out = []
    for r in rows[2:]:
        if len(r) < 3 or not r[0].strip().isdigit():
            continue
        d = {h: (r[i] if i < len(r) else '') for h, i in ix.items()}
        d['ano'] = int(r[0])
        out.append(d)
    return out


def latest_template():
    best = None
    for f in ROOT.glob('*.html'):
        if f.name in ('index.html', 'retornos.html'):
            continue
        c = f.read_text(encoding='utf-8')
        m = re.findall(r'<script id="reuniao-meta" type="application/json">(.*?)</script>', c, re.S)
        if not m:
            continue
        d = datetime.strptime(json.loads(m[-1])['data'], '%d/%m/%Y')
        if best is None or d > best[0]:
            best = (d, f, c)
    return best


def build_data(H, external):
    data = []
    for h in H:
        if h['Produto'] == 'Geral':
            continue
        meta, goog = num(h['Meta Ads']), num(h['Google Ads'])
        midia = (meta or 0) + (goog or 0) if (meta is not None or goog is not None) else (num(h['Mídia Paga']) or 0)
        leads = num(h['Leads']) or 0
        vgv = num(h['VGV']) or 0
        vendas = num(h['Vendas']) or 0
        # venda externa: o VGV fica só no Geral (EXTERNAL_SALES), não no produto
        for e in external:
            if e['ano'] == h['ano'] and e['mes'] == h['Mês'] and e['descricao'].startswith(h['Produto']):
                vgv = max(0, vgv - e['vgv'])
                vendas = max(0, vendas - e['vendas'])
        data.append({"ano": h['ano'], "mes": h['Mês'], "produto": h['Produto'],
                     "midia_paga": round(midia, 2), "leads": leads,
                     "cpl": (midia / leads) if leads else 0,
                     "visitas": num(h['Visitas']) or 0, "vendas": vendas, "vgv": vgv})
    return data


def build_D(H, data, budget_key, budget):
    G = {(h['ano'], h['Mês']): h for h in H if h['Produto'] == 'Geral'}

    def g(y, m, col):
        h = G.get((y, m))
        return (num(h[col]) or 0) if h else 0

    def mp(y, m):  # Mídia Paga do Geral = Meta + Google (o CSV exporta 'Mídia Paga' arredondada, sem centavos)
        h = G.get((y, m))
        if not h:
            return 0
        a, b = num(h['Meta Ads']), num(h['Google Ads'])
        return round((a or 0) + (b or 0), 2) if (a is not None or b is not None) else (num(h['Mídia Paga']) or 0)

    vis = defaultdict(float)
    for d in data:
        vis[(d['ano'], d['mes'])] += d['visitas']
    D = {"geral": {}, "google": {}, "meta": {}}
    for m in MES:
        t = g(2026, m, 'FACs Tentando Contato')
        v = g(2026, m, 'FACs Válidas')
        D["geral"][m] = {"fac_25": g(2025, m, 'FACs Sigavi'), "fac_26": g(2026, m, 'FACs Sigavi'),
                         "valid_25": g(2025, m, 'FACs Válidas'), "valid_26": v,
                         "aprov_25": g(2025, m, '% Tx Aproveitamento'), "aprov_26": g(2026, m, '% Tx Aproveitamento'),
                         "tentando": round(t / v * 100, 2) if v else 0,
                         "cpl_25": g(2025, m, 'CPL'), "cpl_26": g(2026, m, 'CPL'),
                         "invest_25": mp(2025, m), "invest_26": mp(2026, m)}
        for blk, fac, cpl, inv in (("google", 'Cadastro LP - GA', 'CPL Google Ads', 'Google Ads'),
                                   ("meta", 'Cadastros FB', 'CPL Meta Ads', 'Meta Ads')):
            D[blk][m] = {"fac_25": g(2025, m, fac), "fac_26": g(2026, m, fac), "vis_25": 0, "vis_26": 0,
                         "cpl_25": g(2025, m, cpl), "cpl_26": g(2026, m, cpl),
                         "invest_25": g(2025, m, inv), "invest_26": g(2026, m, inv)}
    D["invest"] = {str(y): {m: mp(y, m) for m in MES} for y in (2024, 2025, 2026)}
    D["visitas"] = {str(y): {m: vis[(y, m)] for m in MES} for y in (2025, 2026)}
    D["leads_totais"] = {str(y): {m: int(g(y, m, 'Leads')) for m in MES} for y in (2025, 2026)}
    D["meses"] = MES
    D["budget"] = {budget_key: budget}
    return D


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='dd/mm/aaaa da reunião')
    ap.add_argument('--mes-ref', required=True, help='mês de referência, ex: Outubro')
    ap.add_argument('--dia', type=int, required=True, help='último dia do mês coberto pelos relatórios de mídia')
    ap.add_argument('--budget-meta', type=float, required=True, help='meta de investimento do mês (R$)')
    ap.add_argument('--obs', default=None, help='arquivo JSON com obs_grupos (opcional)')
    ap.add_argument('--csv', default=None, help='CSV local do Histórico (default: baixa do Sheets público)')
    a = ap.parse_args()

    csv_text = Path(a.csv).read_text(encoding='utf-8') if a.csv else subprocess.run(['curl', '-sfL', '-m', '60', CSV_URL], check=True, capture_output=True).stdout.decode('utf-8')
    H = load_hist(csv_text)
    dt = datetime.strptime(a.data, '%d/%m/%Y')
    ano, mes = dt.year, a.mes_ref
    tpl = latest_template()
    if not tpl:
        sys.exit('nenhum template encontrado')
    _, tpl_file, html = tpl
    print('template:', tpl_file.name)

    external = json.loads(re.search(r'const EXTERNAL_SALES = (\[.*?\]);', html, re.S).group(1))
    data = build_data(H, external)
    cal = {m: i for i, m in enumerate(MES)}
    dias_mes = (datetime(ano + (cal[mes] == 11), (cal[mes] + 1) % 12 + 1, 1) - datetime(ano, cal[mes] + 1, 1)).days
    G = {(h['ano'], h['Mês']): h for h in H if h['Produto'] == 'Geral'}
    gm = G[(ano, mes)]
    key = mes.lower().replace('ç', 'c').replace('ã', 'a')
    budget = {"meta": a.budget_meta, "investido": num(gm['Mídia Paga']) or 0, "dia_atual": a.dia, "dias_mes": dias_mes}
    D = build_D(H, data, key, budget)
    mp_mes = D["invest"][str(ano)][mes]
    budget["investido"] = mp_mes

    obs = json.loads(Path(a.obs).read_text(encoding='utf-8')) if a.obs else []
    vis_mes = D["visitas"][str(ano)][mes]
    meta = {"data": a.data, "facs": int(num(gm['FACs Sigavi']) or 0), "validas": int(num(gm['FACs Válidas']) or 0),
            "aprov": num(gm['% Tx Aproveitamento']) or 0, "cpl": int(num(gm['CPL']) or 0),
            "invest": int(mp_mes), "leads": int(num(gm['Leads']) or 0),
            "visitas": int(vis_mes), "mes_ref": f"{mes}/{ano}", "obs_grupos": obs}

    j = lambda o: json.dumps(o, ensure_ascii=False)
    html = re.sub(r'const DATA = \[.*?\];', lambda m: 'const DATA = ' + j(data) + ';', html, count=1, flags=re.S)
    html = re.sub(r'const D = \{.*?\};\n', lambda m: 'const D = ' + j(D) + ';\n', html, count=1, flags=re.S)
    html = re.sub(r'(<script id="reuniao-meta" type="application/json">).*?(</script>)',
                  lambda m: m.group(1) + j(meta) + m.group(2), html, count=1, flags=re.S)
    partial = {"ano": ano, "mes": mes, "dia": a.dia, "dias": dias_mes} if a.dia < dias_mes else None
    html = re.sub(r'const PARTIAL_MONTH = .*?;\n', lambda m: 'const PARTIAL_MONTH = ' + j(partial) + ';\n', html, count=1)
    html = re.sub(r'(id="reportDate">)[^<]*', lambda m: m.group(1) + a.data, html, count=1)
    html = re.sub(r'(id="obsDate">)[^<]*', lambda m: m.group(1) + a.data, html, count=1)

    out = ROOT / f"{dt.day:02d}{ABR[dt.month - 1]}{dt.year}.html"
    out.write_text(html, encoding='utf-8')
    print('gerado:', out.name, '| linhas DATA:', len(data), '| meta:', meta)


if __name__ == '__main__':
    main()
