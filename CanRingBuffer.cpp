#include "CanRingBuffer.h"

// コンストラクタ
CanRingBuffer::CanRingBuffer(size_t bufSize)
    : capacity(bufSize), head(0), tail(0), count(0)
{
    buffer = new CanMessage[capacity];
}

// デストラクタ
CanRingBuffer::~CanRingBuffer() {
    delete[] buffer;
}

// push
bool CanRingBuffer::push(unsigned long id, byte dlc, const byte* data) {
    if (isFull()) return false;

    buffer[head].id = id;
    buffer[head].dlc = dlc;
    for (byte i = 0; i < dlc && i < 8; i++) {
        buffer[head].data[i] = data[i];
    }

    head = (head + 1) % capacity;
    count++;
    return true;
}

// pop
bool CanRingBuffer::pop(unsigned long &id, byte &dlc, byte* data) {
    if (isEmpty()) return false;

    id = buffer[tail].id;
    dlc = buffer[tail].dlc;
    for (byte i = 0; i < dlc && i < 8; i++) {
        data[i] = buffer[tail].data[i];
    }

    tail = (tail + 1) % capacity;
    count--;
    return true;
}

// size
size_t CanRingBuffer::size() const {
    return count;
}

// maxSize
size_t CanRingBuffer::maxSize() const {
    return capacity;
}

// isEmpty
bool CanRingBuffer::isEmpty() const {
    return count == 0;
}

// isFull
bool CanRingBuffer::isFull() const {
    return count == capacity;
}


