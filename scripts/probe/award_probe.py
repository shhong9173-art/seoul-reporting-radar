"""탐침 자리 비움(11-13): 216~222번(단독 데스크 운영 점검)을 마쳤다. 다음 탐침을 쓸 때 이 파일을 바꾼다.
기자 전용 연결 토큰(MCP_ACCESS_TOKEN)은 이 작업 흐름에서 다시 뺐다 — 필요할 때만 넣고, 건수·머리줄만 찍는다."""
open("/tmp/probe_out.txt", "w").write("probe idle")
print("idle")
