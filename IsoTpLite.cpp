#include "IsoTpLite.h"

// ---- ユーティリティ ----
static inline uint8_t min8(uint16_t v){ return (v>255)?255:(uint8_t)v; }

IsoTpLite::IsoTpLite(const Cfg& cfg, SendFn sendFn)
: cfg_(cfg), send_(sendFn) {
  if (cfg_.reasmLimit > BUF_MAX) cfg_.reasmLimit = BUF_MAX;
  reset();
}

void IsoTpLite::reset() {
  st_ = IDLE; expectedLen_ = 0; got_ = 0; nextSn_ = 1;
  bsRemain_ = cfg_.blockSize; tmr_Ncr_ = 0;
}

void IsoTpLite::tick1ms() {
  if (st_ == RECEIVING) {
    if (tmr_Ncr_ > 0) {
      if (--tmr_Ncr_ == 0) abortTimeout();
    }
  }
}

void IsoTpLite::abortTimeout() {
  st_ = ABORT_TIMEOUT;
}

void IsoTpLite::onCanRx(uint32_t id, const uint8_t* d, uint8_t len) {
  if (id != cfg_.rxId || len == 0) return;

  const uint8_t pci = d[0] >> 4;
  //Serial.println(pci,HEX);
  //Serial.println(len);
  switch (pci) {
    case 0x0:  handleSingle(d, len); break;        // SF
    case 0x1:  handleFirst(d, len);  break;        // FF
    case 0x2:  handleConsecutive(d, len); break;   // CF
    case 0x3:  /*FCは受け取らない立場*/ break;
    default:   /*無視*/ break;
  }
}

void IsoTpLite::handleSingle(const uint8_t* d, uint8_t len) {
  // SF: [0]=0x0|DL, [1..] data
  const uint8_t dl = d[0] & 0x0F;
  if (dl > (len-1)) return; // 破損
  if (dl > cfg_.reasmLimit) { st_ = ABORT_OVFL; return; }
  memcpy(buf_, d+1, dl);
  got_ = dl; expectedLen_ = dl; st_ = DONE;
}

void IsoTpLite::handleFirst(const uint8_t* d, uint8_t len) {
  // FF: [0]=0x10|((len>>8)&0x0F), [1]=len&0xFF, [2..] data
  if (len < 8) return; // DLC不足
  uint16_t L = ((d[0] & 0x0F) << 8) | d[1];
  if (L == 0) return; // 非対応（拡張FF長は未対応）
  expectedLen_ = L;
  if (expectedLen_ > cfg_.reasmLimit) {
    sendFC_OVFL(); st_ = ABORT_OVFL; return;
  }
  uint8_t cp = len - 2;                 // FFの同梱データ長
  memcpy(buf_, d+2, cp);
  got_ = cp;
  nextSn_ = 1;
  bsRemain_ = cfg_.blockSize;
  // 受信用タイマを開始（相手のCF到着待ち）
  tmr_Ncr_ = 1000; // 目安：1秒
  // FC(CTS)返信
  sendFC_CTS();
  st_ = RECEIVING;
}

void IsoTpLite::handleConsecutive(const uint8_t* d, uint8_t len) {
  if (st_ != RECEIVING) return;
  const uint8_t sn = d[0] & 0x0F;
  if (sn != (nextSn_ & 0x0F)) return; // SN不一致 → 無視（簡易）
  // データ部
  uint8_t cp = len - 1;
  uint16_t remain = (expectedLen_ > got_) ? (expectedLen_ - got_) : 0;
  if (cp > remain) cp = (uint8_t)remain;
  if (got_ + cp <= cfg_.reasmLimit) {
    memcpy(buf_ + got_, d + 1, cp);
    got_ += cp;
  } else {
    st_ = ABORT_OVFL; return;
  }

  // 完了判定
  if (got_ >= expectedLen_) {
    st_ = DONE;
    tmr_Ncr_ = 0;
    return;
  }

  // ブロック制御
  nextSn_ = (nextSn_ + 1) & 0x0F;
  if (cfg_.blockSize != 0) {
    if (bsRemain_ > 0) bsRemain_--;
    if (bsRemain_ == 0) {
      // 次ブロック許可
      bsRemain_ = cfg_.blockSize;
      sendFC_CTS();
    }
  }
  // 次CF待ちタイマをリロード
  tmr_Ncr_ = 1000; // 目安：1秒
}

bool IsoTpLite::sendFC_CTS() {
  uint8_t fc[8] = { 0 };
  fc[0] = 0x30;                 // FC: CTS
  fc[1] = cfg_.blockSize;       // BS
  fc[2] = cfg_.stmin_ms;        // STmin (ms表現のみ)
  // 残りはパディング0x00でOK
  return send_(cfg_.fcTxId, fc, 8);
}

bool IsoTpLite::sendFC_OVFL() {
  uint8_t fc[8] = { 0 };
  fc[0] = 0x32; // FC: Overflow
  return send_(cfg_.fcTxId, fc, 8);
}

uint16_t IsoTpLite::read(uint8_t* out, uint16_t maxLen) {
  if (st_ != DONE) return 0;
  uint16_t n = (got_ < maxLen) ? got_ : maxLen;
  memcpy(out, buf_, n);
  // 読み出したらリセットして次を受けられるように
  reset();
  return n;
}
