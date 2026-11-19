"""태국 무역구제(상무부 대외무역국 무역구제과 누리집 thaitr.dft.go.th) — 한국산 사건의 새 공고.

근거(11-19 기자 "단독을 위해서 더 노력해봐"): 11-15 다른 매체 단독 「TCC스틸·KG스틸, 태국 반덤핑 재심 대상」은 태국 반덤핑·상계관세위원회
공고(관보 11-11 게재 — 석도강판 AD1212·크롬도금강판 AD1044 일몰재심 중 담보 요구)였다. 레이더는 태국을 보지 않았다.
탐침 23(11-19): 관보 누리집(ratchakitcha.soc.go.th)은 Cloudflare 확인 화면(403)이라 쓰지 않는다(우회하지 않음).
무역구제과 누리집은 로그인 없이 열린다(robots.txt 없음 — 404).
- 목록 /th/search?orderBy=date_desc(약 420KB, 4초): 사건마다 'AD1212 <품목> ที่มีแหล่งกำเนิดจาก : <원산지들> … สถานะ : <상태> AD | ไทยใช้มาตรการ
  วันที่ : 11 พ.ย. 2569'(불기 연도). 'ไทยใช้มาตรการ'=태국이 거는 조치, 'ไทยถูกใช้มาตรการ'=태국산이 당하는 조치(보지 않음).
- 사건 쪽 /th/search/<CASE>(약 210KB): 나라별 세율('สาธารณรัฐเกาหลี ร้อยละ 0 - 22.67 ของราคา ซี ไอ เอฟ'), 징수 시작·끝 날짜,
  공고 PDF(/storage/announcements/…pdf, title 속성에 공고 제목 전문), 조사 단계 표(날짜).
- 공고 PDF: 태국 글자는 글꼴 때문에 깨져 나오지만 영어 업체 이름은 읽힌다('TCC  Steel  Corp.') — 출입처 이름만 찾는다.

하는 일: 원산지에 한국(สาธารณรัฐเกาหลี)이 든 '태국이 거는' 사건, 또는 출입 업종 품목 세이프가드. 목록 날짜가 바뀐 사건만 사건 쪽을 다시 읽고
(한 실행 PAGE_BUDGET건·PAUSE초 간격), 처음 보는 공고 PDF를 이벤트로(PDF는 한 실행 PDF_BUDGET개). 첫 실행·처음 읽는 사건은 기준선.
등급: A = 출입처 이름이 든 개시·재심 개시·담보 요구·관세 부과·종료 공고, 또는 한국산 출입 업종 품목의 개시·부과·종료.
B = 그 밖 한국산 출입 업종 품목 공고. C = 업종 밖 품목. 결과는 기자 전용 저장소(th-trade-remedy)로만 — 공개 로그에는 건수만.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import io
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SCHEMA = "th_trade_remedy/v1"
KST = dt.timezone(dt.timedelta(hours=9))
SITE = "https://thaitr.dft.go.th"
LIST = SITE + "/th/search?orderBy=date_desc"
CASE = SITE + "/th/search/"
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research)"}
PAGE_BUDGET = 4
PDF_BUDGET = 3
PDF_MAX = 8_000_000
PAUSE = 2.0
EVENT_DAYS = 60
KEEP_CASES = 60
KOREA_TH = "สาธารณรัฐเกาหลี"
TH_MONTHS = {"ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6, "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12}
TH_DATE = re.compile(r"(\d{1,2})\s+(ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s+(\d{4})")
# 태국어 품목 → 한국어(보도 대조 낱말). 위에서부터 첫 일치. 없으면 업종 밖.
TH_PRODUCT = [
    (r"ดีบุก", "석도강판", ["석도강판", "석도"]), (r"โครเมียม", "크롬도금강판", ["크롬도금", "TFS"]), (r"รีดร้อน", "열연강판", ["열연"]),
    (r"รีดเย็น", "냉연강판", ["냉연"]), (r"ไร้สนิม|สเตนเลส|สแตนเลส", "스테인리스강", ["스테인리스"]), (r"สังกะสี|อะลูซิงค์", "도금강판", ["도금강판", "도금"]),
    (r"อะลูมิเนียม|อลูมิเนียม", "알루미늄", ["알루미늄"]), (r"ลวดเหล็ก|เหล็กเส้น", "선재·철근", ["선재", "철근"]), (r"ท่อ", "강관", ["강관"]),
    (r"พีวีซี|โพลิไวนิล|โพลีไวนิล", "PVC", ["PVC"]), (r"ยางรถ|ยางนอก", "타이어", ["타이어"]), (r"สายไฟ|สายเคเบิล", "전선", ["전선"]),
    (r"เหล็ก", "철강재", ["철강"]),
]
STRONG = ("조사 개시", "재심 개시", "담보 요구", "관세 부과", "조사 종료")


def now_kst():
    return dt.datetime.now(KST)


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()


def th_date(s):
    """'11 พ.ย. 2569' → '2026-11-11'(불기 −543). 못 읽으면 ''."""
    m = TH_DATE.search(s or "")
    if not m:
        return ""
    try:
        return dt.date(int(m.group(3)) - 543, TH_MONTHS[m.group(2)], int(m.group(1))).isoformat()
    except ValueError:
        return ""


def product_ko(th):
    for rx, ko, words in TH_PRODUCT:
        if re.search(rx, th or ""):
            return ko, words
    return None, []


def kind_of(title):
    """공고 제목(태국어) → 한국어 종류. 순서가 중요하다: 담보 요구 공고 제목에도 '…อากรตอบโต้การทุ่มตลาด'(반덤핑 관세)·'ทบทวน'(재심)이 들어간다."""
    t = title or ""
    if re.search(r"หลักประกัน", t):
        return "담보 요구"
    if re.search(r"เปิด(?:การ)?(?:ไต่สวน|ทบทวน)", t):
        return "재심 개시" if re.search(r"ทบทวน", t) else "조사 개시"
    if re.search(r"ยุติ", t):
        return "조사 종료"
    if re.search(r"ขยายระยะเวลา", t):
        return "기간 연장"
    if re.search(r"แก้ไข", t):
        return "변경·정정"
    if re.search(r"ให้เรียกเก็บอากร|ผลการพิจารณา|กำหนด(?:อัตรา)?อากร", t):
        return "관세 부과"
    return "공고"


BLOCK = re.compile(r"\b((?:AD|CVD|SG|AC)\d{3,5})\s+(.+?)(?:\s+(ที่มีแหล่งกำเนิดจาก|ประเทศผู้ใช้มาตรการ)\s*:\s*(.+?))?\s+ดูเพิ่มเติม\s+"
                   r"สถานะ\s*:\s*(.+?)\s+(AD|CVD|SG|AC)\s*\|\s*(ไทยใช้มาตรการ|ไทยถูกใช้มาตรการ)\s+วันที่\s*:\s*(\d{1,2}\s+\S+\s+\d{4})")


def parse_list(raw):
    """목록 쪽 → [{code, product, countries, status, type, applies, date}] (사건 번호 첫 등장만)."""
    out, seen = [], set()
    for m in BLOCK.finditer(plain(raw)):
        code = m.group(1)
        if code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "product": m.group(2)[:200], "countries": (m.group(4) or "").strip()[:300], "status": m.group(5)[:80],
                    "type": m.group(6), "applies": m.group(7) == "ไทยใช้มาตรการ", "date": th_date(m.group(8))})
    return out


def wanted(c):
    if not c["applies"]:
        return False
    if KOREA_TH in c["countries"]:
        return True
    return c["type"] == "SG" and product_ko(c["product"])[0] is not None


def parse_case(raw):
    """사건 쪽 → {koreaRate, dutyFrom[], dutyTo, announcements:[{url,title}], steps:[{no,label,dates}]}."""
    text = plain(raw)
    out = {"announcements": [], "steps": []}
    seg = text[text.find("อากรที่เรียกเก็บ"):] if "อากรที่เรียกเก็บ" in text else ""
    seg = seg[: seg.find("รายละเอียดตามประกาศ")] if "รายละเอียดตามประกาศ" in seg else seg[:600]
    m = re.search(KOREA_TH + r"\s+ร้อยละ\s+([\d.]+(?:\s*-\s*[\d.]+)?)", seg)
    if m:
        out["koreaRate"] = re.sub(r"\s+", "", m.group(1))
    out["dutyFrom"] = sorted({th_date(x) for x in re.findall(r"วันที่เริ่มต้นเรียกเก็บอากร\s+(\d{1,2}\s+\S+\s+\d{4})", text)} - {""})
    to = [th_date(x) for x in re.findall(r"วันที่สิ้นสุดเรียกเก็บอากร\s+(\d{1,2}\s+\S+\s+\d{4})", text)]
    out["dutyTo"] = max([x for x in to if x], default="")
    seen = set()
    for a in re.finditer(r'<a\s[^>]*href="((?:https?://thaitr\.dft\.go\.th)?/storage/announcements/[^"]+\.pdf)"[^>]*?title="([^"]+)"', raw or ""):
        url = a.group(1) if a.group(1).startswith("http") else SITE + a.group(1)
        if url not in seen:
            seen.add(url)
            out["announcements"].append({"url": url, "title": plain(a.group(2))[:400]})
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", raw or ""):
        c = plain(row)
        s = re.match(r"^(\d+(?:\.\d+)*)\s+(.+?)(?=\s+\d{1,2}\s+\S+\s+\d{4}|$)", c)
        dates = [th_date(x.group(0)) for x in TH_DATE.finditer(c)]
        if s and dates:
            pdf = re.search(r'href=["\']([^"\']+\.pdf)["\']', row, re.I)
            url = (pdf.group(1) if pdf.group(1).startswith("http") else SITE + "/" + pdf.group(1).lstrip("/")) if pdf else ""
            out["steps"].append({"no": s.group(1), "label": s.group(2)[:240], "dates": [d for d in dates if d][:3], **({"pdf": url} if url else {})})
    return out


def step_key(st):
    return f"{st['no']}|{st['label'][:60]}"


def pdf_names(get, url):
    """공고 PDF에서 출입처 영문 이름(태국 글자는 글꼴 때문에 깨진다 — 영어 업체 이름만)."""
    from trade_remedy_watch import BEAT_NAMES
    r = get(url, headers=UA, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    if len(r.content) > PDF_MAX:
        raise RuntimeError("너무 큼")
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(r.content))
    text = re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in rd.pages[:20]))
    names = [n for n, rx in BEAT_NAMES if re.search(rx, text, re.I)]
    return names, len(rd.pages)


def tier_of(kind, names, beat):
    if names and kind in STRONG:
        return "A"
    if beat and kind in ("조사 개시", "관세 부과", "조사 종료"):
        return "A"
    return "B" if beat or names else "C"


def event_of(case, ann, stamp, names, pdf_error=None):
    ko, words = product_ko(case["product"])
    kind = kind_of(ann["title"])
    sg = case["type"] == "SG" and KOREA_TH not in case["countries"]
    text = (f"태국 무역구제 공고 {case['code']} — {kind}: 「{ann['title'][:200]}」 · 품목 {case['product'][:80]}{f'({ko})' if ko else '(출입 업종 밖)'}"
            + (f" · 원산지 {case['countries'][:120]}" if case["countries"] else "")
            + (" · 세이프가드 — 원산지 구분 없이 모든 수입(한국산 포함)" if sg else "")
            + (f" · 한국 세율 {case['koreaRate']}%(CIF 기준, 사건 쪽 표)" if case.get("koreaRate") else "")
            + (f" · 징수 {', '.join(case['dutyFrom'])}~{case['dutyTo'] or '?'}" if case.get("dutyFrom") else "")
            + (f" · 공고 본문(PDF)에 출입처 {'·'.join(names)}" if names else f" · 공고 본문 못 읽음({pdf_error})" if pdf_error else " · 공고 본문(PDF)에 출입처 영문 이름 없음")
            + f" · 상태 「{case['status']}」(목록 날짜 {case['date']}) (태국 반덤핑·상계관세위원회 공고 — 세율·대상 업체는 PDF 원문, 태국어)")
    return {"id": f"thtr:{case['code']}:{ann['url'].rsplit('/', 1)[-1][:60]}", "kind": f"태국 무역구제({kind})", "tier": tier_of(kind, names, ko is not None),
            "code": case["code"], "company": "·".join(names), "companies": names, "product": ko or case["product"][:60], "productWords": words,
            "date": case["date"], "korea": KOREA_TH in case["countries"], **({"safeguard": True} if sg else {}), "url": ann["url"], "caseUrl": CASE + case["code"],
            "text": text, "detectedAt": stamp}


def run(now, previous=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    prev = previous or {}
    first = not prev.get("cases")
    cases = {c["code"]: c for c in prev.get("cases") or [] if isinstance(c, dict) and c.get("code")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict) and str(e.get("detectedAt", "")) >= (now - dt.timedelta(days=EVENT_DAYS)).isoformat()]
    check = {"source": "태국 무역구제과(thaitr.dft.go.th)", "status": "ok", "returned": 0}
    try:
        r = get(LIST, headers=UA, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        listed = parse_list(r.text)
        if not listed:
            raise RuntimeError("목록 0줄(형식 변경 의심)")
    except Exception as e:  # noqa: BLE001
        check.update(status="failed", error=f"목록 {str(e)[:60] or type(e).__name__}")
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": [check], "stale": True} if prev else \
            {"schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": [check], "cases": [], "events": []}
    want = [c for c in listed if wanted(c)]
    check.update(returned=len(listed), korea=len(want))
    errors, budget, pdfs, fresh = [], PAGE_BUDGET, PDF_BUDGET, 0
    prev_listed = set(prev.get("listed") or [])
    for c in sorted(want, key=lambda x: x["date"], reverse=True):
        old = cases.get(c["code"])
        if old and old.get("date") == c["date"] and old.get("read"):
            old.update({k: c[k] for k in ("product", "countries", "status")})
            continue
        # 기준선: 첫 실행, 또는 처음 읽는 사건 중 직전 목록에도 있던 것. 목록에 새로 올라온 사건(한도로 미뤄졌어도)은 공고를 이벤트로
        if old is None:
            baseline = first or c["code"] in prev_listed
        elif not old.get("seen"):
            baseline = not old.get("newCase")
        else:
            baseline = False
        if budget <= 0:
            # 읽어 둔 사건은 옛 목록 날짜를 둔다 — 다음 실행이 날짜가 바뀐 것으로 보고 다시 읽게
            cases[c["code"]] = {**(old or {}), **c, "read": bool(old and old.get("read")), "date": old["date"] if old and old.get("read") else c["date"],
                                "newCase": bool((old or {}).get("newCase")) or (old is None and not baseline)}
            continue
        budget -= 1
        sleep(PAUSE)
        try:
            r = get(CASE + c["code"], headers=UA, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            page = parse_case(r.text)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{c['code']} {str(e)[:30] or type(e).__name__}")
            cases[c["code"]] = {**(old or {}), **c, "read": bool(old and old.get("read")), "date": (old or {}).get("date") if old and old.get("read") else c["date"],
                                "newCase": bool((old or {}).get("newCase")) or (old is None and not baseline)}
            continue
        seen = set((old or {}).get("seen") or [])
        seen_steps = set((old or {}).get("seenSteps") or [])
        rec = {**c, **page, "steps": page["steps"][-12:], "read": True, "readAt": stamp, "url": CASE + c["code"],
               "seen": sorted(seen | {a["url"] for a in page["announcements"]}), "seenSteps": sorted(seen_steps | {step_key(x) for x in page["steps"]})}
        rec.pop("newCase", None)
        rec["productKo"] = product_ko(c["product"])[0]
        new = [a for a in page["announcements"] if a["url"] not in seen]
        # 조사 단계 표에 새 줄(재심 개시 고시 등 — '관련 공고' 칸에는 가장 최근 공고만 남는다, 탐침 23)
        ann_urls = {a["url"] for a in new}
        for st in page["steps"]:
            if step_key(st) in seen_steps or (st.get("pdf") and (st["pdf"] in ann_urls or st["pdf"] in seen)):
                continue
            new.append({"url": st.get("pdf") or f"{CASE}{c['code']}#step-{st['no']}", "title": st["label"], "step": st["no"], "stepDate": max(st["dates"])})
        if not baseline:
            for a in new:
                names, err = [], None
                if not a["url"].lower().endswith(".pdf"):
                    err = "PDF 없음 — 사건 쪽 단계 표"
                elif pdfs > 0:
                    pdfs -= 1
                    sleep(PAUSE)
                    try:
                        names, _ = pdf_names(get, a["url"])
                    except Exception as e:  # noqa: BLE001
                        err = str(e)[:30] or type(e).__name__
                else:
                    err = "실행 한도 — 원문 열기"
                events.append(event_of(rec, a, stamp, names, err))
                fresh += 1
        rec["latest"] = (page["announcements"] or [{}])[0].get("title", "")[:300]
        cases[c["code"]] = rec
    if errors:
        check.update(status="partial", error="; ".join(errors[:3]))
    unread = sum(1 for c in cases.values() if not c.get("read"))
    if unread:
        check["pending"] = unread
    kept = sorted(cases.values(), key=lambda x: x.get("date") or "", reverse=True)[:KEEP_CASES]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": check["status"], "checks": [check], "baselineAt": prev.get("baselineAt") or stamp,
            "listed": [c["code"] for c in listed], "cases": kept, "events": events[-80:], "fresh": fresh,
            "rules": ["태국 무역구제과 누리집(공식). 원산지에 한국이 든 '태국이 거는' 반덤핑·상계관세·우회 사건과 출입 업종 품목 세이프가드만.",
                      "공고 PDF는 태국어(글꼴 때문에 태국 글자는 자동으로 못 읽음) — 출입처 영문 이름만 찾았다. 내용·세율은 원문으로.",
                      "한국 세율은 사건 쪽 '징수 관세' 표의 범위(CIF 기준) — 업체별 세율은 공고 원문. 첫 실행·처음 읽는 사건은 기준선."]}


def main():
    ap = argparse.ArgumentParser(description="태국 무역구제 공고(기자 전용 저장소로)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import private_store
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token and not a.dry_run:
        try:
            previous = private_store.get("th-trade-remedy", token)
        except private_store.StoreError as e:
            print(f"::warning title=th-trade-remedy-state::이전 상태 조회 실패({e}) — 이번에는 저장하지 않는다(기준선을 다시 잡지 않으려고)")
            return 0
    doc = run(now, previous)
    c = doc["checks"][0]
    # 공개 로그에는 건수만(사건·업체·세율은 찍지 않는다)
    print(f"::notice title=th-trade-remedy::상태 {doc['status']} · 목록 {c.get('returned', 0)}건 · 한국·세이프가드 {c.get('korea', 0)} · "
          f"저장 사건 {len(doc.get('cases') or [])} · 이번 새 공고 {doc.get('fresh', 0)}" + (f" · 못 읽은 사건 {c['pending']}" if c.get("pending") else "")
          + (f" · {c['error']}" if c.get("error") else ""))
    if a.dry_run or not token:
        if not token and not a.dry_run:
            print("::warning title=th-trade-remedy-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return 0
    if doc["status"] == "failed" and previous:
        print("::warning title=th-trade-remedy::목록 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("th-trade-remedy", doc, token)
    print(f"::notice title=th-trade-remedy-push::기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
