/*
 * 终极示波器固件 - 标准版 (3电位器 + 10按钮)
 * - 3通道信号: A0, A1, A2
 * - 3电位器: A3(扫描范围), A4(扫描微调), A5(Y轴移位)
 * - 10按钮: D2-D11
 * - 波特率: 250000
 * - 样本数: 200/通道
 */

#define SAMPLES_PER_CHAN 200
#define TOTAL_SAMPLES (3 * SAMPLES_PER_CHAN)  // 600
#define BAUD_RATE 250000

void setup() {
  Serial.begin(BAUD_RATE);
  while (!Serial);
  
  // 配置10个按钮 (D2-D11) 为输入上拉
  for (int pin = 2; pin <= 11; pin++) {
    pinMode(pin, INPUT_PULLUP);
  }
}

void loop() {
  // 发送波形数据帧
  Serial.write(0xAA);
  Serial.write(0x55);
  
  for (int i = 0; i < SAMPLES_PER_CHAN; i++) {
    uint16_t v0 = analogRead(A0);
    uint16_t v1 = analogRead(A1);
    uint16_t v2 = analogRead(A2);
    
    Serial.write(lowByte(v0)); Serial.write(highByte(v0));
    Serial.write(lowByte(v1)); Serial.write(highByte(v1));
    Serial.write(lowByte(v2)); Serial.write(highByte(v2));
  }
  
  // 发送控制数据帧
  Serial.write(0xCC);
  Serial.write(0x33);
  
  // 3个电位器 (A3, A4, A5)
  int pot1 = analogRead(A3);  // 扫描范围
  int pot2 = analogRead(A4);  // 扫描微调
  int pot3 = analogRead(A5);  // Y轴移位
  
  Serial.write(lowByte(pot1)); Serial.write(highByte(pot1));
  Serial.write(lowByte(pot2)); Serial.write(highByte(pot2));
  Serial.write(lowByte(pot3)); Serial.write(highByte(pot3));
  
  // 10个按钮 (D2-D11)
  for (int pin = 2; pin <= 11; pin++) {
    Serial.write(digitalRead(pin) == LOW ? 1 : 0);
  }
  
  delay(10);
}