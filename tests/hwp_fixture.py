"""시험용 HWP 5.0(OLE 복합 문서) 만들기 — 실제 공고문을 저장소에 넣지 않고 hwp_text(파이썬)·hwpText(Aside JS)가 같은 글자를 내는지 본다.
작은 스트림(FileHeader·Section0)은 미니 스트림, 큰 스트림(Section1, 4096바이트 넘음)은 일반 섹터 — 두 읽기 길을 다 지난다."""
import os
import struct
import zlib

SS, MS, CUTOFF = 512, 64, 4096
END, FREE, FATSECT, NOSTREAM = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD, 0xFFFFFFFF


def record(tag, payload):
    size = len(payload)
    if size >= 0xFFF:
        return struct.pack("<I", tag | (0xFFF << 20)) + struct.pack("<I", size) + payload
    return struct.pack("<I", tag | (size << 20)) + payload


def para(text):
    # 문단 글자(67) 앞뒤에 문단 머리(66)·글자 모양(68) 레코드를 섞는다. 글자 안 제어 문자(탭 9·문단 끝 13)도 넣는다
    return record(66, b"\x00" * 22) + record(67, (text + "\t\r").encode("utf-16le")) + record(68, b"\x01\x00\x00\x00\x00\x00\x00\x00")


def deflate_raw(data):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def build(sections, compressed=True, big_noise=6000):
    """sections: 문단 글자 목록의 목록. 마지막 구역에 압축해도 큰 잡음 레코드를 넣어 4096바이트를 넘긴다."""
    header = bytearray(256)
    header[:17] = b"HWP Document File"
    header[36] = 1 if compressed else 0
    streams = [("FileHeader", bytes(header))]
    for n, paras in enumerate(sections):
        raw = b"".join(para(t) for t in paras)
        if n == len(sections) - 1 and big_noise:
            raw += record(87, os.urandom(big_noise))       # 압축이 안 되는 덩어리(그림 같은 것)
        streams.append((f"Section{n}", deflate_raw(raw) if compressed else raw))
    small = [(name, data) for name, data in streams if len(data) < CUTOFF]
    large = [(name, data) for name, data in streams if len(data) >= CUTOFF]

    # 미니 스트림
    ministream, minifat, mini_start = bytearray(), [], {}
    for name, data in small:
        n = -(-len(data) // MS) or 1
        mini_start[name] = len(minifat)
        minifat += [len(minifat) + i + 1 for i in range(n - 1)] + [END]
        ministream += data + b"\x00" * (n * MS - len(data))

    # 섹터 배치: FAT(1) · 디렉터리 · 미니FAT · 미니 스트림 · 큰 스트림
    sectors, fat = [], []

    def alloc(data):
        n = -(-len(data) // SS) or 1
        start = len(sectors)
        for i in range(n):
            sectors.append(bytes(data[i * SS:(i + 1) * SS]).ljust(SS, b"\x00"))
            fat.append(start + i + 1 if i < n - 1 else END)
        return start

    n_dir = -(-(3 + len(streams) - 1) // (SS // 128))
    sectors.append(None); fat.append(FATSECT)                      # 0: FAT
    dir_start = len(sectors); sectors += [None] * n_dir; fat += [2 + i for i in range(n_dir - 1)] + [END]  # 1~: 디렉터리
    minifat_bytes = b"".join(struct.pack("<I", x) for x in minifat)
    minifat_bytes += struct.pack("<I", FREE) * ((-len(minifat_bytes) // 4) % (SS // 4))
    minifat_start = alloc(minifat_bytes)
    ministream_start = alloc(bytes(ministream))
    large_start = {name: alloc(data) for name, data in large}
    assert len(fat) <= SS // 4

    def entry(name, typ, start=0, size=0, left=NOSTREAM, right=NOSTREAM, child=NOSTREAM):
        n = name.encode("utf-16le")
        return (n + b"\x00\x00").ljust(64, b"\x00") + struct.pack("<HBB", len(n) + 2, typ, 1) + struct.pack("<III", left, right, child) \
            + b"\x00" * 36 + struct.pack("<IQ", start, size)

    def where(name, data):
        return (mini_start[name], len(data)) if len(data) < CUTOFF else (large_start[name], len(data))

    by = dict(streams)
    sec_names = [n for n, _ in streams if n.startswith("Section")]
    # 0 Root, 1 FileHeader, 2 BodyText, 3.. Section* — Root 아래: BodyText(왼쪽 FileHeader), BodyText 아래: Section0 → 오른쪽으로 이어짐
    ents = [entry("Root Entry", 5, ministream_start, len(ministream), child=2),
            entry("FileHeader", 2, *where("FileHeader", by["FileHeader"])),
            entry("BodyText", 1, left=1, child=3)]
    for i, name in enumerate(sec_names):
        ents.append(entry(name, 2, *where(name, by[name]), right=(4 + i if i + 1 < len(sec_names) else NOSTREAM)))
    dir_bytes = b"".join(ents).ljust(n_dir * SS, b"\x00")
    for i in range(len(ents), n_dir * SS // 128):   # 빈 칸도 형제·자식 없음
        o = i * 128
        dir_bytes = dir_bytes[:o + 68] + struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM) + dir_bytes[o + 80:]
    for i in range(n_dir):
        sectors[dir_start + i] = dir_bytes[i * SS:(i + 1) * SS]
    sectors[0] = b"".join(struct.pack("<I", x) for x in fat).ljust(SS, b"\xff")

    head = bytearray(SS)
    head[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<HHHHH", head, 0x18, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<I", head, 0x2C, 1)                  # FAT 섹터 수
    struct.pack_into("<I", head, 0x30, dir_start)
    struct.pack_into("<I", head, 0x38, CUTOFF)
    struct.pack_into("<II", head, 0x3C, minifat_start, -(-len(minifat_bytes) // SS))
    struct.pack_into("<II", head, 0x44, END, 0)
    struct.pack_into("<I", head, 0x4C, 0)                   # DIFAT[0] = FAT 섹터 0
    for i in range(1, 109):
        struct.pack_into("<I", head, 0x4C + i * 4, FREE)
    return bytes(head) + b"".join(sectors)
