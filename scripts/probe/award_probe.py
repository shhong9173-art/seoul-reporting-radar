"""Probe 92: 시·도 보도자료(울산·충남·전남광주) 첫 30줄 중 출입처·업종 낱말이 든 제목(거르기 점검용, 공개 목록 제목만, 사이트당 한 번)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
W = re.compile(r"현대|기아|포스코|고려아연|에쓰|S-?OIL|SK|LG|롯데|금호|한화|석유|정유|화학|철강|제철|자동차|수소|전력|배터리|이차전지|산단|산업단지|투자|협약|기업")
out = []
for name, url, params in [("울산", "https://www.ulsan.go.kr/u/rep/bbs/list.ulsan?bbsId=BBS_0000000000000027&mId=001004003001000000", {}),
                          ("충남", "https://www.chungnam.go.kr/cnportal/cnapcPressList/cnapcPress/list.do?menuNo=500498", {"pageUnit": "30"}),
                          ("전남광주", "https://www.jeonnam-gwangju.go.kr/boardList.do?boardId=JG_0000000003&pageId=jngj22", {"recordCnt": "30"})]:
    try:
        r = requests.get(url, params=params, headers=H, timeout=30)
        titles = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m)).strip() for m in re.findall(r'<a[^>]+href="[^"]*(?:dataId|nttId|seq)=\d+[^"]*"[^>]*>(.*?)</a>', r.text, re.S)]
        hit = [t for t in titles if W.search(t)]
        out.append(f"{name} HTTP {r.status_code} titles {len(titles)} hits {len(hit)}")
        for t in hit[:12]:
            out.append(f"  {t[:80]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{name} {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
