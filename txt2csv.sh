sed -E 's/^([0-9.]+)s since last ([0-9A-Fa-f]+) \| \(([0-9.]+)\).*/\3,\2,\1/' delta.txt > delta.csv

