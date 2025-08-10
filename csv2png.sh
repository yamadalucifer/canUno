python3 - <<'PY'
import csv, collections, matplotlib.pyplot as plt
xs = collections.defaultdict(list)
ys = collections.defaultdict(list)

with open("delta.csv") as f:
    for epoch, cid, dt in csv.reader(f):
        xs[cid].append(float(epoch))
        ys[cid].append(float(dt)*1000)  # ms

for cid in sorted(xs):
    if cid == "456":
        plt.scatter(xs[cid], ys[cid], label=cid, s=9, color='orange', alpha=0.1)
    else:
        plt.scatter(xs[cid], ys[cid], label=cid, s=9, alpha=0.1)

plt.xlabel("Epoch (s)")
plt.ylabel("Δt (ms)")
plt.title("Per-ID Δt")
plt.legend()
plt.tight_layout()
plt.savefig("delta.png", dpi=150)
print("saved delta.png")
PY



