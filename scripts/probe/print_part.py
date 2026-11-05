import sys
blob = open("/tmp/probe_out.txt").read()
p = int(sys.argv[1])
level = ["notice", "warning", "error"][p]
for i in range(p * 13000, min(len(blob), (p + 1) * 13000), 1300):
    print(f"::{level} title=sp-{i // 1300:02d}::{blob[i:i + 1300]}".replace("\n", "%0A"))
