"""probe 255: USTR 2027 NTE 의견서(USTR-2026-0498) 첨부 본문에서 한국 + 출입 업종 대목 찾기. 공개 정부 자료만. 저장 안 함."""
import collections
import datetime as dt
import io
import os
import re
import time

import requests

OUT = []
UA = {"User-Agent": "Mozilla/5.0 (seoul-reporting-radar probe)", "Accept": "application/json"}
KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "").strip() or "DEMO_KEY"
API = "https://api.regulations.gov/v4"
T0 = time.time()
KOREA = re.compile(r"(?<!North )(?<!north )\bKorea(?:n|ns|'s)?\b|\bKORUS\b|\bROK\b|Republic of Korea")
BEAT = re.compile(r"steel|automo|vehicle|\bcars?\b|\btires?\b|chemical|petrochem|refin|transformer|electrical equipment|cable|solar|batter|zinc|copper|alumin|hydrogen|emission|fuel econom|K-REACH|electricity|\bEVs?\b|Hyundai|\bKia\b|POSCO|Hanwha|Lotte|LG Chem|SK Innovation|Korea Zinc|epoxy|resin|polymer|ethylene|nuclear|LNG|ethanol|biofuel|rubber|lubricant", re.I)
DOCKET = "USTR-2026-0498"


def reg(path, params=None):
    for attempt in range(2):
        try:
            r = requests.get(API + path, params={**(params or {}), "api_key": KEY}, headers=UA, timeout=40)
            time.sleep(1.0)
            if r.status_code == 429:
                time.sleep(20)
                continue
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}"
            return r.json(), None
        except Exception as e:  # noqa: BLE001
            err = type(e).__name__
    return None, "재시도 실패"


def pdf_text(data, pages=90):
    import pypdf
    out = []
    try:
        pdf = pypdf.PdfReader(io.BytesIO(data))
        for i, p in enumerate(pdf.pages):
            if i >= pages:
                break
            try:
                out.append(p.extract_text() or "")
            except Exception:  # noqa: BLE001
                out.append("")
        return re.sub(r"[ \t]+", " ", "\n".join(out)), len(pdf.pages)
    except Exception as e:  # noqa: BLE001
        return "", f"PDF 실패 {type(e).__name__}"


def main():
    rows, page = [], 1
    while page <= 2:
        body, err = reg("/comments", {"filter[docketId]": DOCKET, "sort": "postedDate", "page[size]": "250", "page[number]": str(page)})
        if err:
            OUT.append(f"목록 실패 {err}")
            break
        rows += body.get("data") or []
        if not (body.get("meta") or {}).get("hasNextPage"):
            break
        page += 1
    OUT.append(f"[NTE 2027 · {DOCKET}] 의견서 {len(rows)}건")
    stats = collections.Counter()
    hits, others = [], []
    for x in rows:
        if time.time() - T0 > 1500:
            stats["시간 한도로 못 읽음"] += 1
            continue
        cid = x.get("id")
        title = re.sub(r"^Comment (?:from|submitted by)\s+", "", str((x.get("attributes") or {}).get("title") or ""))[:70]
        body, err = reg(f"/comments/{cid}", {"include": "attachments"})
        if err:
            stats[f"상세 {err}"] += 1
            continue
        text = str(((body.get("data") or {}).get("attributes") or {}).get("comment") or "")
        npages = 0
        files = []
        for inc in body.get("included") or []:
            for f in (inc.get("attributes") or {}).get("fileFormats") or []:
                if str(f.get("format")).lower() == "pdf" and f.get("fileUrl"):
                    files.append(f["fileUrl"])
        for url in files[:3]:
            try:
                r = requests.get(url, headers={"User-Agent": UA["User-Agent"]}, timeout=60)
                if r.status_code != 200 or len(r.content) > 25_000_000:
                    stats[f"첨부 HTTP {r.status_code}"] += 1
                    continue
                t, n = pdf_text(r.content)
                if isinstance(n, int):
                    npages += n
                else:
                    stats[n] += 1
                text += "\n" + t
            except Exception as e:  # noqa: BLE001
                stats[f"첨부 {type(e).__name__}"] += 1
        stats["읽음"] += 1
        if not files:
            stats["첨부 없음"] += 1
        if len(text) < 400 and files:
            stats["글자 못 뽑음(스캔본?)"] += 1
        ms = list(KOREA.finditer(text))
        if not ms:
            continue
        beat = []
        for m in ms:
            ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 350):m.end() + 450])
            words = sorted({w.group(0).lower() for w in BEAT.finditer(ctx)})
            if words:
                beat.append((len(words), words, ctx))
        if beat:
            beat.sort(key=lambda b: -b[0])
            hits.append((len(beat), cid, title, len(ms), npages, beat))
        else:
            others.append(f"{title}({len(ms)})")
    OUT.append(f"   읽기: {dict(stats)} · 한국 언급 {len(hits) + len(others)}건 · 그중 출입 업종 낱말 곁에 있는 것 {len(hits)}건 · {time.time() - T0:.0f}초")
    hits.sort(key=lambda h: -h[0])
    for nbeat, cid, title, nk, npages, beat in hits[:34]:
        words = sorted({w for _, ws, _ in beat for w in ws})
        OUT.append(f"■ {title} | {cid} | {npages}쪽 | 한국 {nk}곳·업종 곁 {nbeat}곳 | 낱말 {', '.join(words)[:150]}")
        shown = 0
        seen = set()
        for _, ws, ctx in beat:
            k = ctx[300:380]
            if k in seen:
                continue
            seen.add(k)
            OUT.append(f"   «{ctx[110:640]}»")
            shown += 1
            if shown >= (2 if nbeat >= 3 else 1):
                break
    OUT.append("   한국 언급은 있으나 업종 낱말 없는 곳: " + " / ".join(others[:40]))
    # 관보 2026-20341이 말하는 협정
    try:
        r = requests.get("https://www.federalregister.gov/api/v1/documents/2026-20341.json", headers=UA, timeout=30).json()
        OUT.append(f"[관보 2026-20341] {r.get('title')} | 의견 마감 {r.get('comments_close_on')} | {str(r.get('abstract'))[:400]}")
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[관보 2026-20341] 실패 {type(e).__name__}")
    for dk in ("USTR-2026-0595", "USTR-2026-0596", "USTR-2026-0364", "USTR-2026-0661"):
        body, err = reg("/comments", {"filter[docketId]": dk, "sort": "-postedDate", "page[size]": "40"})
        if err:
            OUT.append(f"[{dk}] 실패 {err}")
            continue
        rows = body.get("data") or []
        OUT.append(f"[{dk}] 의견서 {(body.get('meta') or {}).get('totalElements')}건: " + " / ".join(re.sub(r"^Comment (?:from|submitted by)\s+", "", str((x.get('attributes') or {}).get('title')))[:42] for x in rows[:26]))


try:
    main()
except Exception as e:  # noqa: BLE001
    OUT.append(f"예외 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
