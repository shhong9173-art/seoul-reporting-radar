"""Probe 79: (1) 공정위 보도자료 게시판 목록 칸(제목·날짜·부서) 형식, (2) 공공데이터포털 정책브리핑 API(policyNewsService2) 공유 키 응답 —
정책뉴스와 보도자료 목록 연산 후보를 한 번씩. 공개 보도자료 제목·부처명만 몇 줄, 키 값은 남기지 않는다."""
import os
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
KEY = os.environ.get("DATA_GO_KR_KEY", "")


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", s)).strip()


for key, ctg in [("12", "01,02"), ("13", "03")]:
    try:
        r = requests.get("https://www.ftc.go.kr/www/selectBbsNttList.do", params={"bordCd": "3", "key": key, "searchCtgry": ctg}, headers=H, timeout=30)
        out.append(f"ftc key={key} HTTP {r.status_code} len {len(r.text)}")
        body = r.text.split("<tbody", 1)[-1].split("</tbody>", 1)[0]
        trs = re.split(r"<tr[\s>]", body)[1:]
        out.append(f"  rows {len(trs)}")
        for tr in trs[:4]:
            cells = [clean(c)[:60] for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            href = re.search(r'href="([^"]*nttSn=\d+[^"]*)"', tr)
            onclick = re.search(r"onclick=\"([^\"]{0,120})\"", tr)
            out.append(f"  cells {cells}")
            out.append(f"  href {(href.group(1) if href else '')[:120]} onclick {(onclick.group(1) if onclick else '')[:100]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"ftc {type(e).__name__} {str(e)[:80]}")

base = "https://apis.data.go.kr/1371000/policyNewsService2"
for op in ["policyNewsList", "pressReleaseList"]:
    try:
        r = requests.get(f"{base}/{op}", params={"serviceKey": KEY, "startDate": "20261029", "endDate": "20261031"}, headers=H, timeout=40)
        t = r.text
        code = re.search(r"<resultCode>([^<]*)</resultCode>", t)
        msg = re.search(r"<resultMsg>([^<]*)</resultMsg>", t) or re.search(r"<returnAuthMsg>([^<]*)</returnAuthMsg>", t)
        reason = re.search(r"<returnReasonCode>([^<]*)</returnReasonCode>", t)
        items = re.findall(r"<NewsItem>(.*?)</NewsItem>", t, re.S)
        out.append(f"api {op} HTTP {r.status_code} len {len(t)} code {code.group(1) if code else '-'} msg {(msg.group(1) if msg else '')[:60]} reason {reason.group(1) if reason else '-'} items {len(items)}")
        if not items:
            out.append("  head " + clean(t[:300]).replace(KEY, "<KEY>")[:300])
        tags = sorted(set(re.findall(r"<([A-Za-z]+)>", items[0])))[:30] if items else []
        out.append(f"  tags {tags}")
        mins = {}
        for it in items:
            m = re.search(r"<MinisterCode>([^<]*)</MinisterCode>", it)
            mins[m.group(1) if m else "?"] = mins.get(m.group(1) if m else "?", 0) + 1
        out.append(f"  ministries {sorted(mins.items(), key=lambda x: -x[1])[:15]}")
        for it in items[:4]:
            ti = re.search(r"<Title>(.*?)</Title>", it, re.S)
            ap = re.search(r"<ApproveDate>([^<]*)</ApproveDate>", it)
            out.append(f"  {(ap.group(1) if ap else '')[:20]} | {clean(ti.group(1) if ti else '')[:60]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"api {op} {type(e).__name__} {str(e)[:80]}")
text = "\n".join(out)
if KEY:
    text = text.replace(KEY, "<KEY>")
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
