#ifndef CANRINGBUFFER_H
#define CANRINGBUFFER_H

#include <Arduino.h>

class CanRingBuffer {
private:
    struct CanMessage {
        unsigned long id;      // CAN ID
        byte dlc;               // Data Length Code
        byte data[8];           // データ
    };

    CanMessage* buffer;         // 動的確保したバッファ
    size_t capacity;            // バッファの最大長
    size_t head;                // 書き込み位置
    size_t tail;                // 読み出し位置
    size_t count;               // 現在の格納数

public:
    // コンストラクタ
    CanRingBuffer(size_t bufSize);

    // デストラクタ
    ~CanRingBuffer();

    // データ追加（満杯ならfalseを返す）
    bool push(unsigned long id, byte dlc, const byte* data);

    // データ取得（空ならfalseを返す）
    bool pop(unsigned long &id, byte &dlc, byte* data);

    // 現在の格納数
    size_t size() const;

    // 最大容量
    size_t maxSize() const;

    // 空判定
    bool isEmpty() const;

    // 満杯判定
    bool isFull() const;
};

#endif
