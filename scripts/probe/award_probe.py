"""격리 탐침 48: 무역구제 기관 목록 더 — 영국 TRA·인도네시아 KADI·말레이시아·베트남·태국·튀르키예·브라질·멕시코·GCC·EU 진행 사건. 접속·'Korea' 줄 수·예."""
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import trade_remedy_watch as t  # noqa: E402

KOREA = re.compile(r"korea|corée|coreia|corea|\bkore\b|hàn quốc|เกาหลี", re.I)
URLS = [
    ("uk-tra", "https://www.trade-remedies.service.gov.uk/public/cases/"),
    ("id-kadi", "https://kadi.kemendag.go.id/"),
    ("id-kadi-en", "https://kadi.kemendag.go.id/en/"),
    ("my-miti", "https://www.miti.gov.my/index.php/pages/view/2807"),
    ("vn-trav", "https://www.trav.gov.vn/"),
    ("vn-trav-en", "https://www.trav.gov.vn/en/"),
    ("th-dft", "https://www.dft.go.th/en-us/"),
    ("tr-ticaret", "https://www.ticaret.gov.tr/ithalat/ticaret-politikasi-savunma-araclari/damping-ve-subvansiyon"),
    ("br-gecex", "https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/defesa-comercial-e-interesse-publico/investigacoes"),
    ("mx-se", "https://www.gob.mx/se/acciones-y-programas/practicas-comerciales-internacionales"),
    ("gcc", "https://www.gcc-sg.org/en/CooperationAndAchievements/Achievements/EconomicCooperation/TradeRemedies"),
    ("eu-tron", "https://tron.trade.ec.europa.eu/investigations/ongoing"),
    ("eu-ojc", "https://eur-lex.europa.eu/oj/direct-access.html"),
    ("za-itac", "https://www.itac.org.za/pages/trade-remedies/current-investigations"),
    ("ph-dti", "https://www.dti.gov.ph/trade-remedies/"),
    ("ar-cnce", "https://www.argentina.gob.ar/produccion/cnce"),
]


def probe(item):
    pid, url = item
    try:
        r = requests.get(url, headers=t.HEADERS, timeout=40)
        raw = r.text
        lines = []
        for chunk in re.split(r"(?i)<br\s*/?>|</(?:p|tr|li|div|h\d|td|a)>", raw):
            s = t.plain(chunk)
            if KOREA.search(s) and 8 <= len(s) <= 300:
                lines.append(s)
        lines = list(dict.fromkeys(lines))
        return f"{pid} HTTP {r.status_code} len={len(raw)} korea줄={len(lines)} 예={lines[:3]}"
    except Exception as e:  # noqa: BLE001
        return f"{pid} {type(e).__name__}"


with ThreadPoolExecutor(8) as ex:
    out = list(ex.map(probe, URLS))
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
