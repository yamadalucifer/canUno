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

void loop() {
  //rx 
  if (CAN.checkReceive() == CAN_MSGAVAIL) {
    long unsigned int rxId;
    unsigned char len;
    unsigned char rxBuf[8];
    CAN.readMsgBuf(&len, rxBuf);
    rxId = CAN.getCanId();
    Serial.print("ID: ");
    Serial.print(rxId, HEX);
    Serial.print(" Data: ");
    for (byte i = 0; i < len; i++) {
      Serial.print(rxBuf[i], HEX);
      Serial.print(" ");
    }
    Serial.println();
    if(rxRingBuf.push(rxId,len,rxBuf)==false){
      Serial.println("BufferFull");
    };
  }
  //proc
  if(rxRingBuf.isEmpty()==false){
    unsigned long id;
    byte dlc;
    byte data[8];
    if(rxRingBuf.pop(id,dlc,data)){
      if(id==0x123){
        txRingBuf.push(0x456,dlc,data);
      }
    }
  }
  //tx
  if(txRingBuf.isEmpty()==false){
    unsigned long id;
    byte dlc;
    byte data[8];
    if(txRingBuf.pop(id,dlc,data)){
      CAN.sendMsgBuf(id,0,dlc,data);
    }
  }
}
