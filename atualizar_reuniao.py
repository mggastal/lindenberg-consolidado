#!/usr/bin/env python3
"""
atualizar_reuniao.py — atualiza TUDO da reunião semanal de uma vez:
  1) baixa a planilha Leadform Lindenberg (aba "Sigavi Relatório") e regenera o relatório Motivos de Descarte;
  2) baixa o Histórico do Revenue Board e gera o HTML da reunião (gerar_snapshot.py);
  3) copia o relatório de descartes para DDmmmAAAA-descartes.html (aba "Descartes" do Revenue Board).

Uso:
  python atualizar_reuniao.py --data 22/10/2026 --mes-ref Outubro --dia 22 --budget-meta 398000
  (opcionais: --sem-sigavi  não baixa o Sigavi de novo | --csv hist.csv  Histórico local | --obs obs.json)

Não faz git push — publicar é um passo separado, depois de conferir.
"""
import argparse, hashlib, os, subprocess, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DESC_DIR = ROOT.parent / 'Lindenberg' / 'Motivos de Descarte'
SIGAVI_ID = '18HDMPHpp4Ug-jWYx2PpWG_boAqUSvnnHxKwvLU69Org'
SIGAVI_URL = f'https://docs.google.com/spreadsheets/d/{SIGAVI_ID}/export?format=xlsx'


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def atualizar_sigavi():
    dados = DESC_DIR / 'dados'
    dados.mkdir(exist_ok=True)
    novo, atual = dados / 'sigavi_novo.xlsx', dados / 'sigavi.xlsx'
    subprocess.run(['curl', '-sfL', '-m', '300', '-o', str(novo), SIGAVI_URL], check=True)
    if novo.stat().st_size < 1_000_000:
        novo.unlink()
        sys.exit('Sigavi: download inesperado (arquivo muito pequeno) — a planilha continua pública?')
    if atual.exists() and md5(atual) == md5(novo):
        novo.unlink()
        print('Sigavi: planilha sem mudanças desde o último download')
        return False
    if atual.exists():
        bkp = dados / f"sigavi_{datetime.fromtimestamp(atual.stat().st_mtime):%Y-%m-%d}.xlsx"
        if not bkp.exists():
            atual.rename(bkp)
    novo.replace(atual)
    print('Sigavi: planilha atualizada')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--mes-ref', required=True)
    ap.add_argument('--dia', type=int, required=True)
    ap.add_argument('--budget-meta', type=float, required=True)
    ap.add_argument('--obs', default=None)
    ap.add_argument('--csv', default=None)
    ap.add_argument('--sem-sigavi', action='store_true')
    a = ap.parse_args()

    if not a.sem_sigavi:
        atualizar_sigavi()
    subprocess.run([sys.executable, str(DESC_DIR / 'gerar_relatorio.py')], check=True, cwd=DESC_DIR)

    cmd = [sys.executable, str(ROOT / 'gerar_snapshot.py'), '--data', a.data, '--mes-ref', a.mes_ref,
           '--dia', str(a.dia), '--budget-meta', str(a.budget_meta)]
    if a.obs:
        cmd += ['--obs', a.obs]
    if a.csv:
        cmd += ['--csv', a.csv]
    subprocess.run(cmd, check=True, cwd=ROOT)
    print('\nPronto. Confira e depois publique (git add/commit/push).')


if __name__ == '__main__':
    main()
