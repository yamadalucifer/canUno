#include <mcp2515_can.h>
#include <SPI.h>
#include "CanRingBuffer.h"

mcp2515_can CAN(9);
CanRingBuffer rxRingBuf(8);
CanRingBuffer txRingBuf(8);

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  if (CAN.begin(CAN_500KBPS) == CAN_OK) {
    Serial.println("CAN init OK!");
  } else {
    Serial.println("CAN init FAIL!");
    while (1)
      ;
  }
}

// 前回の処理時刻（マイクロ秒）
unsigned long prevProcMicros = 0;

void loop() {
  //rx 
  while (CAN.checkReceive() == CAN_MSGAVAIL) {
    //Serial.println("rx");
    long unsigned int rxId;
    unsigned char len;
    unsigned char rxBuf[8];
    CAN.readMsgBuf(&len, rxBuf);
    rxId = CAN.getCanId();
    //Serial.print("ID: ");
    //Serial.print(rxId, HEX);
    //Serial.print(" Data: ");
    //for (byte i = 0; i < len; i++) {
    //  Serial.print(rxBuf[i], HEX);
    //  Serial.print(" ");
    //}
    //Serial.println();
    if(rxRingBuf.push(rxId,len,rxBuf)==false){
      Serial.println("BufferFull");
    };
  }

  //proc を1msごとに実行
  unsigned long nowMicros = micros();
  if (nowMicros - prevProcMicros >= 1000) { // 1000µs = 1ms
    //Serial.println("proc");
    prevProcMicros += 1000;  // 誤差蓄積を防ぐため加算方式
    while(rxRingBuf.isEmpty()==false){
      //Serial.println("rx2txBuf");
      unsigned long id;
      byte dlc;
      byte data[8];
      if(rxRingBuf.pop(id,dlc,data)){
        //Serial.println(id);
        if(id==0x123){
          //Serial.println("valid id");
          txRingBuf.push(0x456,dlc,data);
        }
      }
    }
  }
  //tx
  uint8_t sent = 0;
  const uint8_t TX_MAX = 8;
  while((txRingBuf.isEmpty()==false)&&(sent < TX_MAX)){
    unsigned long id;
    byte dlc;
    byte data[8];
    if(txRingBuf.pop(id,dlc,data)){
      if(CAN_OK == CAN.sendMsgBuf(id,0,dlc,data)){
        
      }else{
        break;
      }
    }
    sent++;
  }
}
