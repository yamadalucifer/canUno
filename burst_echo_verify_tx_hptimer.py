#!/usr/bin/env python3
# file: burst_echo_verify_tx_hptimer.py
"""
高精度送信版
- time.sleep 依存を避け、time.perf_counter による「定間隔（steady pacing）」で送信
- 送信と受信をスレッド分離（干渉を最小化）
- 送信完了後も一定時間受信継続し、取りこぼしを減らす
- 送信ループバックと UNO 応答を別々に集計（重複検出あり）
"""

import time
import struct
import threading
import queue
import gc
import sys

try:
    import can
except Exception as e:
    print("python-can が必要です: pip install python-can")
    raise

# ====== 設定 ======
CHANNEL = "can0"
SEND_ID = 0x123      # PC→UNO
ECHO_ID = 0x456      # UNO→PC (エコー)
FRAME_COUNT = 10000
DLC = 8
#PACED_MS = 0.57      # None でバースト送信 / 0.57 など小数可
#PACED_MS = 4.00      # None でバースト送信 / 0.57 など小数可
PACED_MS = 3.50      # None でバースト送信 / 0.57 など小数可
RECV_GRACE_S = 3.0   # 送信終了後、受信を続ける猶予時間
BUS_SEND_TIMEOUT = 0.05  # bus.send のタイムアウト

# ====== 便利関数 ======
def make_payload(seq: int, dlc: int):
    data = bytearray([0xAA] * dlc)
    struct.pack_into(">H", data, 0, seq & 0xFFFF)
    return bytes(data)

# ====== 送信スレッド ======
def sender_task(bus: "can.Bus", tx_done_evt: threading.Event, paced_ms: float | None):
    t0 = time.perf_counter()
    interval = (paced_ms / 1000.0) if paced_ms else 0.0

    # 送信ループ
    for seq in range(FRAME_COUNT):
        msg = can.Message(arbitration_id=SEND_ID, is_extended_id=False,
                          data=make_payload(seq, DLC))
        try:
            bus.send(msg, timeout=BUS_SEND_TIMEOUT)
        except can.CanError as e:
            # 送信失敗はログ出しのみで継続
            print(f"[SEND ERR] seq={seq}: {e}", file=sys.stderr)

        if interval > 0.0:
            # 次フレームの理想送信時刻（steady pacing）
            target = t0 + (seq + 1) * interval
            # oversleep を避けるため短時間スリープ + 再チェック
            while True:
                now = time.perf_counter()
                remain = target - now
                if remain <= 0:
                    break
                # 50µs 単位で細かく待つ（CPU 負荷と精度の妥協点）
                # OS により分解能は異なるため必要に応じて 0.00002 などに調整
                time.sleep(0.00005)

    tx_done_evt.set()

# ====== 受信スレッド ======
def receiver_task(reader: "can.BufferedReader", rx_q: "queue.Queue", stop_evt: threading.Event):
    # reader.get_message() は内部バッファから取り出す
    while not stop_evt.is_set():
        msg = reader.get_message(timeout=0.05)
        if msg is None:
            continue
        rx_q.put(msg)

# ====== メイン ======
def main():
    print("High-Precision CAN burst/echo verify starting...")

    # GC を先に実行して送信ループ中の GC 発火確率を下げる
    gc.collect()

    # Bus 構築（ループバックも拾う）
    bus = can.Bus(interface="socketcan", channel=CHANNEL, receive_own_messages=True)

    # フィルタ設定（SEND_ID, ECHO_ID のみ通す）
    bus.set_filters([
        {"can_id": SEND_ID, "can_mask": 0x7FF, "extended": False},
        {"can_id": ECHO_ID, "can_mask": 0x7FF, "extended": False},
    ])

    # Notifier + BufferedReader（受信専用スレッドからキューへ流す）
    reader = can.BufferedReader()
    notifier = can.Notifier(bus, [reader])

    rx_q: "queue.Queue[can.Message]" = queue.Queue(maxsize=100000)
    stop_evt = threading.Event()
    rx_thr = threading.Thread(target=receiver_task, args=(reader, rx_q, stop_evt), daemon=True)
    rx_thr.start()

    # 送信スレッド
    tx_done_evt = threading.Event()
    tx_thr = threading.Thread(target=sender_task, args=(bus, tx_done_evt, PACED_MS), daemon=True)

    # タイミング計測開始
    t_send_start = time.perf_counter()
    tx_thr.start()

    # 送信完了待ち
    tx_thr.join()
    t_send_end = time.perf_counter()

    # 送信完了後もしばらく受信継続
    grace_deadline = time.perf_counter() + RECV_GRACE_S
    while time.perf_counter() < grace_deadline:
        time.sleep(0.01)

    # 受信停止
    stop_evt.set()
    rx_thr.join(timeout=0.5)
    notifier.stop()
    bus.shutdown()

    # -------- 集計 --------
    sent_looped = set()   # SEND_ID（ループバック）
    echoed = set()        # ECHO_ID（UNO 応答）
    dup_loop = dup_echo = 0

    while not rx_q.empty():
        msg = rx_q.get_nowait()
        data = msg.data if msg.data is not None else b""
        if len(data) < 2:
            continue
        seq = struct.unpack_from(">H", data, 0)[0]

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

    duration_send = t_send_end - t_send_start
    tx_rate = (FRAME_COUNT / duration_send) if duration_send > 0 else 0.0
    lost_loop = FRAME_COUNT - len(sent_looped)
    lost_echo = FRAME_COUNT - len(echoed)

    print("===== RESULT (High-Precision) =====")
    print(f"TX attempted:     {FRAME_COUNT}")
    print(f"TX loopback OK:   {len(sent_looped)}  (lost={lost_loop})")
    print(f"ECHO received:    {len(echoed)}       (lost={lost_echo})")
    print(f"Duplicates:       loop={dup_loop} echo={dup_echo}")
    print(f"Send duration:    {duration_send*1000:.1f} ms  (~{tx_rate:.0f} fps)")
    if PACED_MS:
        print(f"Pacing interval:  {PACED_MS} ms (steady pacing via perf_counter)")
    else:
        print("Pacing interval:  burst (no pacing)")

    # 欠番リストの先頭のみ表示（多すぎると重いので）
    if lost_loop:
        miss = sorted(set(range(FRAME_COUNT)) - sent_looped)[:20]
        print(f"Missing TX loopback seq (first 20): {miss}{' ...' if lost_loop>20 else ''}")
    if lost_echo:
        miss = sorted(set(range(FRAME_COUNT)) - echoed)[:20]
        print(f"Missing ECHO seq (first 20): {miss}{' ...' if lost_echo>20 else ''}")

if __name__ == "__main__":
    main()
