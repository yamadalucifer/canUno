#pragma once
#include <Arduino.h>

class IsoTpLite {
public:
  // 下位層送信関数: return true=送信受理
  using SendFn = bool(*)(uint32_t can_id, const uint8_t* data, uint8_t len);

  struct Cfg {
    uint32_t rxId;     // 受信するISO-TP ID（例: 0x7E0 物理要求）
    uint32_t fcTxId;   // FlowControlを送るID（例: 0x7E0へ送ってくる相手の送信元IDに対応する相手宛ID。通常は同一ID系）
    uint8_t  stmin_ms; // FC.STmin (0..0x7F=ms). Unoなら 1〜5 推奨
    uint8_t  blockSize;// FC.BlockSize (0=無限, 4〜8推奨)
    uint16_t reasmLimit;// 再組立て上限（最大受信長）例: 64
  };

  enum Status : uint8_t {
    IDLE, RECEIVING, DONE, ABORT_OVFL, ABORT_TIMEOUT
  };

  explicit IsoTpLite(const Cfg& cfg, SendFn sendFn);

  // 1msごとに呼んでタイマ処理
  void tick1ms();

  // 下位CANからの受信（IDとペイロード）
  void onCanRx(uint32_t id, const uint8_t* data, uint8_t len);

  // 完了データ取得（DONE時のみ有効）
  uint16_t read(uint8_t* out, uint16_t maxLen);

  Status status() const { return st_; }
  void   reset();

private:
  // 内部
  bool sendFC_CTS();     // Continue To Send
  bool sendFC_OVFL();    // Buffer Overflow
  void handleSingle(const uint8_t* d, uint8_t len);
  void handleFirst(const uint8_t* d, uint8_t len);
  void handleConsecutive(const uint8_t* d, uint8_t len);
  void abortTimeout();

  // config
  Cfg cfg_;
  SendFn send_;

  // state
  Status  st_ = IDLE;
  uint16_t expectedLen_ = 0; // 総長
  uint16_t got_ = 0;         // 受信済み
  uint8_t  nextSn_ = 1;      // 次に期待するSN (1..15)
  uint8_t  bsRemain_ = 0;    // 残りCF数（BlockSize制御用）
  uint16_t tmr_Ncr_ = 0;     // 連続CF待ちタイマ(ms)

  // バッファ（最大reasmLimit）
  static const uint16_t BUF_MAX = 64;
  uint8_t buf_[BUF_MAX];
};
