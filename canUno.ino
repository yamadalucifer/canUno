#include <mcp2515_can.h>
#include <SPI.h>
#include "CanRingBuffer.h"
#include "IsoTpLite.h"

mcp2515_can CAN(9);
// 下位送信関数
bool canSendShim(uint32_t id, const uint8_t* d, uint8_t len){
  return CAN.sendMsgBuf(id, 0, len, const_cast<uint8_t*>(d)) == CAN_OK;
}

// UDS物理: 0x7E0 を受け、FCは 0x7E0 に返す想定（相手機による）
IsoTpLite::Cfg isocfg = {
  .rxId = 0x7E0,
  .fcTxId = 0x7A0,   // 通常は相手が送ってくるIDに返す。必要に応じて 0x7E8 等に変更
  .stmin_ms = 5,     // 安全運転ライン
  .blockSize = 8,
  .reasmLimit = 64
};
IsoTpLite isotp(isocfg, canSendShim);

CanRingBuffer rxRingBuf;
CanRingBuffer txRingBuf;
volatile bool canInt = false;
void canISR(){
  canInt = true;
}
void canHwToSw(){
  while ((CAN.checkReceive() == CAN_MSGAVAIL)) {
    long unsigned int rxId;
    unsigned char len;
    unsigned char rxBuf[8];
    CAN.readMsgBuf(&len, rxBuf);
    rxId = CAN.getCanId();
    //Serial.print("len ");
    //Serial.println(len);
    
    if(rxRingBuf.push(rxId,len,rxBuf)==false){
      //Serial.println("BufferFull");
    };
  }
}
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
  //CAN.init_Mask(0,0,0x7FF);

  //CAN.init_Filt(0,0,0x123);//for test
  //CAN.init_Filt(1,0,0x7E0);//for uds

  //CAN.init_Mask(1,0,0x7FF);

  //CAN.init_Filt(2,0,0x7E0);//for uds
  //CAN.init_Filt(3,0,0x123);//for test
  //CAN.init_Filt(4,0,0x7FF);
  //CAN.init_Filt(5,0,0x7FF);

  attachInterrupt(digitalPinToInterrupt(2), canISR, FALLING);
}

// 前回の処理時刻（マイクロ秒）
unsigned long prevProcMicros = 0;

void loop() {
  //rx 
  if(canInt){
    canInt = false;
    canHwToSw();
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
        }else if(id==0x7E0){
          //Serial.print("id ");
          //Serial.println(id,HEX);
          //Serial.print("dlc ");
          //Serial.println(dlc);
          isotp.onCanRx(id, data, dlc);
        }else{

        }
      }
    }
    isotp.tick1ms();
  }
  //rx
  if(canInt){
    canInt = false;
    canHwToSw();
  }
    // 3) 完了チェック
  if (isotp.status() == IsoTpLite::DONE) {
    uint8_t rx[64];
    uint16_t n = isotp.read(rx, sizeof(rx));
    // ここでUDS AP層処理（例：サービスID確認など）
    // …必要なら応答送信は今後の送信実装で対応
    for(int i = 0; i < n; i++){
      Serial.print(rx[i],HEX);
      Serial.print(" ");
    }
    Serial.println("");
  }
  //rx
  if(canInt){
    canInt = false;
    canHwToSw();
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
        //while(true){
        //  if(CAN_OK == CAN.sendMsgBuf(id,0,dlc,data)){
        //    break;
        //  }
        //}
        //Serial.println("tx fail");
        break;
      }
    }
    sent++;
  }
}
