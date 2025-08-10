candump -t a can0 | python3 -u -c '
import sys, time
last = {}
for line in sys.stdin:
    parts = line.strip().split()
    if len(parts) < 3: continue
    t = float(parts[0].strip("()"))      # epoch秒
    can_id = parts[1]                    # can0 またはID列？→candump -t a だと [1]=can0 [2]=ID
    if can_id.startswith("can"):
        can_id = parts[2]
    dt = t - last.get(can_id, t)
    last[can_id] = t
    print(f"{dt:.6f}s since last {can_id} | {line.strip()}")
'

