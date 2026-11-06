"""probe 198: GitHub 러너에서 경남 보도자료 게시판·기후부(me.go.kr) 접속 — 11-06 기자 컴퓨터(Aside)에서는 경남 200(1.1초), me.go.kr은 이름 풀기 실패. 저장 안 함."""
import socket, time
import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


UA = {"User-Agent": "Mozilla/5.0 (seoul-reporting-radar probe)"}
for host in ("www.gyeongnam.go.kr", "me.go.kr", "www.me.go.kr"):
    try:
        log(host, "DNS", sorted({x[4][0] for x in socket.getaddrinfo(host, 443)})[:4])
    except Exception as e:  # noqa: BLE001
        log(host, "DNS 실패", type(e).__name__, str(e)[:80])
for url in ("https://www.gyeongnam.go.kr/board/list.gyeong?boardId=BBS_0000060&menuCd=DOM_000000135002001000&contentsSid=6959&cpath=",
            "https://me.go.kr/home/web/main.do"):
    for timeout in (20, 45):
        t = time.time()
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            log(url[:60], timeout, "HTTP", r.status_code, len(r.content), f"{time.time() - t:.1f}s", "보도자료" in r.text)
            break
        except Exception as e:  # noqa: BLE001
            log(url[:60], timeout, type(e).__name__, str(e)[:100], f"{time.time() - t:.1f}s")
        time.sleep(2)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
