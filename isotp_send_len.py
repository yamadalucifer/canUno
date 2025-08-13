#!/usr/bin/env python3
# file: isotp_send_len.py
"""
Length-based ISO-TP sender wrapper.
Usage:
  python3 isotp_send_len.py 65 -v
  python3 isotp_send_len.py 32 --channel can0 --tx-id 0x7E0 --fc-id 0x7E8

It reuses isotp_send.py's run() to perform the actual ISO-TP segmentation.
Generates a test payload of the requested length: 0x01,0x02,...
"""
import argparse, sys

def make_payload(length: int) -> bytes:
    if length < 1 or length > 65:
        raise ValueError("length must be in 1..65")
    # bytes from 1..length (wrap not needed within 65)
    return bytes(range(1, length+1))

def main():
    ap = argparse.ArgumentParser(description="Send ISO-TP payload of given length (1..65)")
    ap.add_argument("length", type=int, help="payload length (1..65)")
    ap.add_argument("--channel", default="can0")
    ap.add_argument("--tx-id", type=lambda x:int(x,0), default=0x7E0)
    ap.add_argument("--fc-id", type=lambda x:int(x,0), default=0x7A0)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    payload = make_payload(args.length)

    try:
        from isotp_send import run  # reuse the tested sender
    except Exception as e:
        print("[ERR] Could not import isotp_send.run. Ensure isotp_send.py is in the same directory.", file=sys.stderr)
        raise

    rc = run(args.channel, args.tx_id, args.fc_id, payload, args.verbose)
    sys.exit(rc)

if __name__ == "__main__":
    main()
