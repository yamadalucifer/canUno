#!/usr/bin/env python3
# file: isotp_send.py
"""
Simple ISO-TP (ISO 15765-2) sender for SocketCAN.
- Sends Single Frame (SF) when payload <= 7 bytes.
- Otherwise sends First Frame (FF) then Consecutive Frames (CF),
  honoring Flow Control (FC) from the receiver (CTS/WAIT/OVFL).
- Supports STmin in ms (0x00..0x7F) and 100us steps (0xF1..0xF9).
- Uses time.perf_counter() for steady pacing.

Typical usage (tester -> ECU at 500kbps):
  python3 isotp_send.py --channel can0 --tx-id 0x7E0 --fc-id 0x7E8 --data 22F190

Notes:
- tx-id : arbitration ID used to SEND our segments (tester->ECU)
- fc-id : arbitration ID from which we EXPECT Flow Control (ECU->tester)
- This tool does NOT assemble responses; it only sends the request properly.
"""

import argparse, time, struct, sys, binascii
import can

def parse_hex_bytes(s: str) -> bytes:
    s = s.strip().replace(' ', '').replace('-', '').replace('_', '')
    if s.startswith('0x') or s.startswith('0X'):
        s = s[2:]
    if len(s) % 2 != 0:
        raise ValueError("hex length must be even")
    try:
        return binascii.unhexlify(s)
    except Exception as e:
        raise ValueError(f"invalid hex: {e}")

def stmin_to_seconds(v: int) -> float:
    # 0x00..0x7F => milliseconds
    if 0x00 <= v <= 0x7F:
        return v / 1000.0
    # 0xF1..0xF9 => 100us steps (0xF1=100us, 0xF9=900us)
    if 0xF1 <= v <= 0xF9:
        return (v - 0xF0) * 100e-6
    # 0xF0 or 0x80..0x8F are reserved/invalid here -> treat as 0
    return 0.0

def send_frame(bus: can.Bus, tx_id: int, data: bytes):
    if len(data) > 8:
        raise ValueError("CAN frame > 8 bytes")
    pad = data + bytes(max(0, 8 - len(data)))
    msg = can.Message(arbitration_id=tx_id, is_extended_id=False, data=pad)
    bus.send(msg, timeout=0.1)

def wait_for_fc(reader: can.BufferedReader, fc_id: int, timeout_s: float = 1.0):
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        msg = reader.get_message(timeout=0.05)
        if msg is None:
            continue
        if msg.arbitration_id != fc_id or msg.dlc < 3:
            continue
        pci_type = (msg.data[0] >> 4) & 0xF
        if pci_type != 0x3:
            # Not FC, ignore
            continue
        fs = msg.data[0] & 0xF  # 0=CTS,1=WAIT,2=OVFL
        bs = msg.data[1]
        stmin = msg.data[2]
        return fs, bs, stmin, msg.data[:8]
    return None, None, None, None

def run(channel: str, tx_id: int, fc_id: int, payload: bytes, verbose: bool):
    bus = can.Bus(interface="socketcan", channel=channel, receive_own_messages=False)
    # Only listen for FC from fc_id to reduce load
    bus.set_filters([{"can_id": fc_id, "can_mask": 0x7FF, "extended": False}])
    reader = can.BufferedReader()
    notifier = can.Notifier(bus, [reader])

    try:
        n = len(payload)
        if verbose:
            print(f"[INFO] TX-ID=0x{tx_id:03X}  FC-ID=0x{fc_id:03X}  len={n}")

        if n <= 7:
            # Single Frame
            sf = bytes([ (0x0 << 4) | n ]) + payload
            if verbose:
                print(f"[SF] {sf.hex()}")
            send_frame(bus, tx_id, sf)
            return 0

        # Multi-frame: First Frame
        if n > 0xFFF:
            print("[ERR] payload too long for 12-bit FF length (max 4095 bytes).", file=sys.stderr)
            return 2

        ff_len_hi = (n >> 8) & 0x0F
        ff_len_lo = n & 0xFF
        take = min(6, n)
        ff = bytes([ (0x1 << 4) | ff_len_hi, ff_len_lo ]) + payload[:take]
        if verbose:
            print(f"[FF] {ff.hex()}")
        send_frame(bus, tx_id, ff)

        # Wait for FC
        while True:
            fs, bs, stmin, raw = wait_for_fc(reader, fc_id, timeout_s=1.0)
            if fs is None:
                print("[ERR] FC timeout (N_Bs).", file=sys.stderr)
                return 3
            if verbose:
                print(f"[FC] raw={raw.hex()}  FS={fs}  BS={bs}  STmin=0x{stmin:02X} ({stmin_to_seconds(stmin)*1000:.3f} ms)")
            if fs == 0x2:
                print("[ERR] FC=Overflow from receiver.", file=sys.stderr)
                return 4
            if fs == 0x1:
                # WAIT: keep waiting (simple handling)
                if verbose: print("[FC] WAIT ...")
                continue
            if fs == 0x0:
                break  # CTS

        # Send CFs honoring BS & STmin
        st_gap = stmin_to_seconds(stmin)
        sn = 1
        sent = take
        bs_remain = bs if bs != 0 else None  # None means unlimited
        t_last = time.perf_counter()

        while sent < n:
            chunk = payload[sent: sent + 7]
            cf = bytes([ (0x2 << 4) | (sn & 0x0F) ]) + chunk
            # Enforce STmin (steady pacing)
            if st_gap > 0:
                target = t_last + st_gap
                while True:
                    now = time.perf_counter()
                    if now >= target:
                        break
                    # short sleep to reduce busy-wait
                    time.sleep(0.00005)
            send_frame(bus, tx_id, cf)
            t_last = time.perf_counter()
            if verbose:
                print(f"[CF sn={sn%16}] {cf.hex()}")
            sent += len(chunk)
            sn = (sn + 1) & 0x0F

            if bs_remain is not None:
                bs_remain -= 1
                if bs_remain == 0 and sent < n:
                    # Need next FC
                    if verbose:
                        print("[FC] waiting for next CTS ...")
                    fs, bs, stmin, raw = wait_for_fc(reader, fc_id, timeout_s=1.0)
                    if fs is None:
                        print("[ERR] FC timeout (N_Bs).", file=sys.stderr); return 5
                    if fs == 0x2:
                        print("[ERR] FC=Overflow from receiver.", file=sys.stderr); return 6
                    if fs == 0x1:
                        # WAIT: in simple form keep waiting for CTS
                        while fs == 0x1:
                            if verbose: print("[FC] WAIT ...")
                            fs, bs, stmin, raw = wait_for_fc(reader, fc_id, timeout_s=1.0)
                            if fs is None:
                                print("[ERR] FC timeout (N_Bs).", file=sys.stderr); return 7
                    # Update pacing & BS
                    st_gap = stmin_to_seconds(stmin)
                    bs_remain = bs if bs != 0 else None

        if verbose:
            print("[DONE] All segments sent.")
        return 0

    finally:
        notifier.stop()
        bus.shutdown()

def main():
    ap = argparse.ArgumentParser(description="Simple ISO-TP sender (SocketCAN)")
    ap.add_argument("--channel", default="can0")
    ap.add_argument("--tx-id", type=lambda x:int(x,0), default=0x7E0, help="tester->ECU arbitration ID (e.g., 0x7E0)")
    ap.add_argument("--fc-id", type=lambda x:int(x,0), default=0x7E8, help="ECU->tester FC arbitration ID (e.g., 0x7E8)")
    ap.add_argument("--data", required=True, help="hex payload (e.g., 22F190)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    payload = parse_hex_bytes(args.data)
    rc = run(args.channel, args.tx_id, args.fc_id, payload, args.verbose)
    sys.exit(rc)

if __name__ == "__main__":
    main()
