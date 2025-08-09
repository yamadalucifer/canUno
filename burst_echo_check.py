# file: burst_echo_verify_tx.py
import time, struct
import can

CHANNEL = "can0"
SEND_ID = 0x123      # PC→UNO
ECHO_ID = 0x456      # UNO→PC (エコー)
FRAME_COUNT = 10000
DLC = 8
#PACED_MS = None      # None=バースト, 1=1ms など
PACED_MS = 1      # None=バースト, 1=1ms など
RECV_TIMEOUT_S = 3.0

def make_payload(seq: int, dlc: int):
    data = bytearray([0xAA]*dlc)
    struct.pack_into(">H", data, 0, seq & 0xFFFF)
    return bytes(data)

def main():
    # ★ 自分の送信フレームも受信する
    bus = can.Bus(interface="socketcan", channel=CHANNEL, receive_own_messages=True)

    # SEND_ID(ループバック) と ECHO_ID(UNOの応答) の両方を拾う
    bus.set_filters([
        {"can_id": SEND_ID, "can_mask": 0x7FF, "extended": False},
        {"can_id": ECHO_ID, "can_mask": 0x7FF, "extended": False},
    ])

    reader = can.BufferedReader()
    notifier = can.Notifier(bus, [reader])

    # --- 送信 ---
    t0 = time.time()
    for seq in range(FRAME_COUNT):
        msg = can.Message(arbitration_id=SEND_ID, is_extended_id=False,
                          data=make_payload(seq, DLC))
        try:
            bus.send(msg, timeout=0.1)
        except can.CanError as e:
            print(f"[SEND ERR] seq={seq}: {e}")
            # ここで直帰せず続行でもOK
        if PACED_MS is not None:
            time.sleep(PACED_MS/1000.0)
    t1 = time.time()

    # --- 受信（送信ループバックと応答を別々に集計） ---
    sent_looped = set()   # 送信成功の証跡（SEND_IDが自分に返る）
    echoed = set()        # 応答受信（ECHO_ID）
    dup_loop = dup_echo = 0

    deadline = time.time() + RECV_TIMEOUT_S
    while time.time() < deadline and (len(sent_looped) < FRAME_COUNT or len(echoed) < FRAME_COUNT):
        msg = reader.get_message(timeout=0.05)
        if msg is None:
            continue
        if len(msg.data) < 2:
            continue
        seq = struct.unpack_from(">H", msg.data, 0)[0]

        if msg.arbitration_id == SEND_ID:
            if seq in sent_looped:
                dup_loop += 1
            else:
                sent_looped.add(seq)

        elif msg.arbitration_id == ECHO_ID:
            if seq in echoed:
                dup_echo += 1
            else:
                echoed.add(seq)

    notifier.stop(); bus.shutdown()

    # --- 結果 ---
    duration_send = t1 - t0
    tx_rate = FRAME_COUNT/duration_send if duration_send>0 else 0
    lost_loop = FRAME_COUNT - len(sent_looped)
    lost_echo = FRAME_COUNT - len(echoed)

    print("===== RESULT =====")
    print(f"TX attempted: {FRAME_COUNT}")
    print(f"TX loopback OK: {len(sent_looped)}  (lost={lost_loop})")
    print(f"ECHO received: {len(echoed)}       (lost={lost_echo})")
    print(f"Duplicates: loop={dup_loop} echo={dup_echo}")
    print(f"Send duration: {duration_send*1000:.1f} ms  (~{tx_rate:.0f} fps)")

    if lost_loop:
        miss = sorted(set(range(FRAME_COUNT)) - sent_looped)[:20]
        print(f"Missing TX loopback seq (first 20): {miss}{' ...' if FRAME_COUNT-len(sent_looped)>20 else ''}")
    if lost_echo:
        miss = sorted(set(range(FRAME_COUNT)) - echoed)[:20]
        print(f"Missing ECHO seq (first 20): {miss}{' ...' if FRAME_COUNT-len(echoed)>20 else ''}")

if __name__ == "__main__":
    main()
