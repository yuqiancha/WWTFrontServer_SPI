import codecs
import time as t
import threading
from binascii import hexlify
from datetime import *
from Data import MyLock
from Data import SharedMemory
from PyQt5 import QtCore
from PyQt5.QtCore import *
import urllib.parse
from serial422 import RS422Func
import logging.config
from os import path
import configparser
import threading
from Data import MyLock
from Data import SharedMemory
from PyQt5.QtCore import *

import spidev,time
import sys,cmd,shlex,types
from mcp2515 import *

import logging
MyLog = logging.getLogger('ws_debug_log')       #log data
MajorLog = logging.getLogger('ws_error_log')      #log error

class CanServer(QThread):
    signal = pyqtSignal(str)

    signal_newLock = pyqtSignal(MyLock)
    signal_Lock = pyqtSignal(MyLock)

    def __init__(self):
        super(CanServer,self).__init__()
        MyLog.debug('CanServer in')

        self.spi = spidev.SpiDev(0, 0)

        self.mcp2515_init()

        self.WaitCarComeTime = int(120)  # 等待车子停进来的时间，2min不来就升锁
        self.WaitCarLeaveTime = int(300)  # 车子停进来前5min，依旧是2min升锁，超出时间立刻升锁
        self.AfterCarLeaveTime = int(10)  # 超出5min，认为车子是要走了，1min升锁

        try:
            cf = configparser.ConfigParser()
            cf.read(path.expandvars('$HOME') + '/Downloads/WWTFrontServer_SPI/Configuration.ini', encoding="utf-8-sig")

            self.WaitCarComeTime = cf.getint("StartLoad", "WaitCarComeTime")
            self.WaitCarLeaveTime = cf.getint("StartLoad", "WaitCarLeaveTime")
            self.AfterCarLeaveTime = cf.getint("StartLoad", "AfterCarLeaveTime")
        except Exception as ex:
            MajorLog(ex + 'From openfile /waitcartime')

        MyLog.debug("WaitCarComeTime:" + str(self.WaitCarComeTime))
        MyLog.debug("WaitCarLeaveTime:" + str(self.WaitCarLeaveTime))
        MyLog.debug("AfterCarLeaveTime:" + str(self.AfterCarLeaveTime))

        global stridList
        stridList = []

        self.mtimer = QTimer()
        self.mtimer.timeout.connect(self.LockAutoDown)
        self.mtimer.start(1000)

        self.mtimer2 = QTimer()
        self.mtimer2.timeout.connect(self.WaitCarStatusDisable)
        self.mtimer2.start(1000)

        pass



    def mcp2515_reset(self):
        tmpc = [0xc0]
        self.spi.writebytes(tmpc)

    def mcp2515_writeReg(self,addr,val):
        buf = [0x02, addr, val]
        self.spi.writebytes(buf)

    def mcp2515_readReg(self,addr):
        buf = [0x03, addr, 0x55]
        buf = self.spi.xfer2(buf)
        return int(buf[2])

    def mcp2515_init(self):
        print("spi start init----")
        self.mcp2515_reset()
        time.sleep(2)
        # 设置波特率为125Kbps
        # set CNF1,SJW=00,长度为1TQ,BRP=49,TQ=[2*(BRP+1)]/Fsoc=2*50/8M=12.5us
        self.mcp2515_writeReg(CNF1, CAN_100Kbps);

        # set CNF2,SAM=0,在采样点对总线进行一次采样，PHSEG1=(2+1)TQ=3TQ,PRSEG=(0+1)TQ=1TQ
        self.mcp2515_writeReg(CNF2, 0x80 | PHSEG1_3TQ | PRSEG_1TQ);

        # mcp2515_writeReg(CNF2, 0x80|PHSEG1_3TQ|PRSEG_1TQ)  # //0x80|PHSEG1_3TQ|PRSEG_1TQ);

        # set CNF3,PHSEG2=(2+1)TQ=3TQ,同时当CANCTRL.CLKEN=1时设定CLKOUT引脚为时间输出使能位
        self.mcp2515_writeReg(CNF3, PHSEG2_3TQ);

        self.mcp2515_writeReg(TXB0SIDH, 0xC1)  # 发送缓冲器0标准标识符高位
        self.mcp2515_writeReg(TXB0SIDL, 0x09)  # 发送缓冲器0标准标识符低位(第3位为发送拓展标识符使能位)
        self.mcp2515_writeReg(TXB0EID8, 0xFD)  # 发送缓冲器0拓展标识符高位
        self.mcp2515_writeReg(TXB0EID0, 0xFA)  # 发送缓冲器0拓展标识符低位

        self.mcp2515_writeReg(RXB0SIDH, 0x00)  # 清空接收缓冲器0的标准标识符高位
        self.mcp2515_writeReg(RXB0SIDL, 0x00)  # 清空接收缓冲器0的标准标识符低位
        self.mcp2515_writeReg(RXB0EID8, 0x00)  # 清空接收缓冲器0的拓展标识符高位
        self.mcp2515_writeReg(RXB0EID0, 0x00)  # 清空接收缓冲器0的拓展标识符低位
        self.mcp2515_writeReg(RXB0CTRL, 0x64)  # 仅仅接收拓展标识符的有效信息
        self.mcp2515_writeReg(RXB0DLC, DLC_8)  # 设置接收数据的长度为8个字节

        self.mcp2515_writeReg(RXF0SIDH, 0xFF)  # 配置验收滤波寄存器n标准标识符高位
        self.mcp2515_writeReg(RXF0SIDL, 0xE3)  # 配置验收滤波寄存器n标准标识符低位(第3位为接收拓展标识符使能位)
        self.mcp2515_writeReg(RXF0EID8, 0xFA)  # 配置验收滤波寄存器n拓展标识符高位
        self.mcp2515_writeReg(RXF0EID0, 0xFD)  # 配置验收滤波寄存器n拓展标识符低位

        self.mcp2515_writeReg(RXM0SIDH, 0x00)  # 配置验收屏蔽寄存器n标准标识符高位
        self.mcp2515_writeReg(RXM0SIDL, 0x00)  # 配置验收屏蔽寄存器n标准标识符低位
        self.mcp2515_writeReg(RXM0EID8, 0xFF)  # 配置验收滤波寄存器n拓展标识符高位
        self.mcp2515_writeReg(RXM0EID0, 0x00)  # 配置验收滤波寄存器n拓展标识符低位


        self.mcp2515_writeReg(RXB1SIDH, 0x00)  # 清空接收缓冲器0的标准标识符高位
        self.mcp2515_writeReg(RXB1SIDL, 0x00)  # 清空接收缓冲器0的标准标识符低位
        self.mcp2515_writeReg(RXB1EID8, 0x00)  # 清空接收缓冲器0的拓展标识符高位
        self.mcp2515_writeReg(RXB1EID0, 0x00)  # 清空接收缓冲器0的拓展标识符低位
        self.mcp2515_writeReg(RXB1CTRL, 0x60)  # 仅仅接收拓展标识符的有效信息
        self.mcp2515_writeReg(RXB1DLC, DLC_8)  # 设置接收数据的长度为8个字节

        self.mcp2515_writeReg(RXF1SIDH, 0xFF)  # 配置验收滤波寄存器n标准标识符高位
        self.mcp2515_writeReg(RXF1SIDL, 0xEB)  # 配置验收滤波寄存器n标准标识符低位(第3位为接收拓展标识符使能位)
        self.mcp2515_writeReg(RXF1EID8, 0xFF)  # 配置验收滤波寄存器n拓展标识符高位
        self.mcp2515_writeReg(RXF1EID0, 0xFF)  # 配置验收滤波寄存器n拓展标识符低位

        self.mcp2515_writeReg(RXM1SIDH, 0xFF)  # 配置验收屏蔽寄存器n标准标识符高位
        self.mcp2515_writeReg(RXM1SIDL, 0xE3)  # 配置验收屏蔽寄存器n标准标识符低位
        self.mcp2515_writeReg(RXM1EID8, 0xFF)  # 配置验收滤波寄存器n拓展标识符高位
        self.mcp2515_writeReg(RXM1EID0, 0xFF)  # 配置验收滤波寄存器n拓展标识符低位



        self.mcp2515_writeReg(CANINTF, 0x00)  # 清空CAN中断标志寄存器的所有位(必须由MCU清空)
        self.mcp2515_writeReg(CANINTE, 0x03)  # 配置CAN中断使能寄存器的接收缓冲器0满中断使能,其它位禁止中断

        self.mcp2515_writeReg(CANCTRL, REQOP_NORMAL | CLKOUT_ENABLED)  # 将MCP2515设置为正常模式,退出配置模式

        # tmpc = mcp2515_readReg(CANSTAT)#读取CAN状态寄存器的值
        # tmpd = int(tmpc[0]) & 0xe0
        # if OPMODE_NORMAL!=tmpd:#判断MCP2515是否已经进入正常模式
        #    mcp2515_writeReg(CANCTRL,REQOP_NORMAL|CLKOUT_ENABLED)#再次将MCP2515设置为XX模式,退出配置模式
        print("spi finish init----")

    def mcp2515_write(self,buf):
        for i in range(50):
            time.sleep(0.5)  # 通过软件延时约nms(不准确)
            if not self.mcp2515_readReg(TXB0CTRL) & 0x08:  # 快速读某些状态指令,等待TXREQ标志清零
                break
        N = len(buf)
        for j in range(N):
            self.mcp2515_writeReg(TXB0D0 + j, buf[j])  # 将待发送的数据写入发送缓冲寄存器

            self.mcp2515_writeReg(TXB0DLC, N)  # 将本帧待发送的数据长度写入发送缓冲器0的发送长度寄存器
            self.mcp2515_writeReg(TXB0CTRL, 0x08)  # 请求发送报文

    def mcp2515_read(self):
        N = 0
        buf = []

        if self.mcp2515_readReg(CANINTF) & 0x03 == 0x03 :
            print("INTF-03  "+hex(self.mcp2515_readReg(CANINTF)))
            print("CANSTAT-03  " + hex(self.mcp2515_readReg(CANSTAT)))

            t1 = self.mcp2515_readReg(RXB0SIDH)
            t2 = self.mcp2515_readReg(RXB0SIDL)
            t3 = self.mcp2515_readReg(RXB0EID8)
            t4 = self.mcp2515_readReg(RXB0EID0)

            buf.append(t1>>3)
            buf.append((t2&0x03)+((t2&0xE0)>>3)+((t1&0x07)<<5))
            buf.append(t3)
            buf.append(t4)

            N = self.mcp2515_readReg(RXB0DLC)  # 读取接收缓冲器0接收到的数据长度(0~8个字节)
            for i in range(N):
                buf.append(self.mcp2515_readReg(RXB0D0 + i))  # 把CAN接收到的数据放入指定缓冲区

            t1 = self.mcp2515_readReg(RXB1SIDH)
            t2 = self.mcp2515_readReg(RXB1SIDL)
            t3 = self.mcp2515_readReg(RXB1EID8)
            t4 = self.mcp2515_readReg(RXB1EID0)

            buf.append(t1>>3)
            buf.append((t2&0x03)+((t2&0xE0)>>3)+((t1&0x07)<<5))
            buf.append(t3)
            buf.append(t4)

            M = self.mcp2515_readReg(RXB1DLC)  # 读取接收缓冲器0接收到的数据长度(0~8个字节)
            for i in range(M):
                buf.append(self.mcp2515_readReg(RXB1D0 + i))  # 把CAN接收到的数据放入指定缓冲区

        elif self.mcp2515_readReg(CANINTF) & 0x01:
            print("INTF-01  "+hex(self.mcp2515_readReg(CANINTF)))
            print("CANSTAT-01  " + hex(self.mcp2515_readReg(CANSTAT)))
            N = self.mcp2515_readReg(RXB0DLC)  # 读取接收缓冲器0接收到的数据长度(0~8个字节)

            t1 = self.mcp2515_readReg(RXB0SIDH)
            t2 = self.mcp2515_readReg(RXB0SIDL)
            t3 = self.mcp2515_readReg(RXB0EID8)
            t4 = self.mcp2515_readReg(RXB0EID0)

            buf.append(t1>>3)
            buf.append((t2&0x03)+((t2&0xE0)>>3)+((t1&0x07)<<5))
            buf.append(t3)
            buf.append(t4)

            for i in range(N):
                buf.append(self.mcp2515_readReg(RXB0D0 + i))  # 把CAN接收到的数据放入指定缓冲区

        elif self.mcp2515_readReg(CANINTF) & 0x02==0x02:
            print("INTF-02  "+hex(self.mcp2515_readReg(CANINTF)))
            print("CANSTAT-02  " + hex(self.mcp2515_readReg(CANSTAT)))

            t1 = self.mcp2515_readReg(RXB1SIDH)
            t2 = self.mcp2515_readReg(RXB1SIDL)
            t3 = self.mcp2515_readReg(RXB1EID8)
            t4 = self.mcp2515_readReg(RXB1EID0)

            buf.append(t1>>3)
            buf.append((t2&0x03)+((t2&0xE0)>>3)+((t1&0x07)<<5))
            buf.append(t3)
            buf.append(t4)
            M = self.mcp2515_readReg(RXB1DLC)  # 读取接收缓冲器0接收到的数据长度(0~8个字节)
            for i in range(M):
                 buf.append(self.mcp2515_readReg(RXB1D0 + i))  # 把CAN接收到的数据放入指定缓冲区
        else:
            pass

        self.mcp2515_writeReg(CANINTF, 0)  # 清除中断标志位(中断标志寄存器必须由MCU清零)
        return buf



    def LockAutoDown(self):  # 定时器调用，检测无车满60s后自动发送升锁指令
        for lock in SharedMemory.LockList:
            if lock.arm == '10':
                if lock.car == '00':
                    lock.nocaron += 1
                else:
                    lock.nocaron = 0

                if lock.nocaron >= self.WaitCarComeTime and lock.waitcar == False:  # 降锁后等待车子来停
                    lock.nocaron = 0

                    self.sendToCan(lock.addr + '02')

                    lock.carLeave = datetime.now()
                    lock.reservd2 = datetime.strftime(lock.carLeave, '%Y-%m-%d %H:%M:%S')

                    lock.carStayTime = (str(lock.carLeave - lock.carCome).split('.'))[0]

                    lock.reservd3 = lock.carStayTime
                    self.signal_Lock.emit(lock)
                    t.sleep(0.05)

                if lock.nocaron >= self.AfterCarLeaveTime and lock.carFinallyLeave == True:  # 车子离开等待60s就升锁
                    lock.carFinallyLeave = True
                    lock.nocaron = 0

                    self.sendToCan(lock.addr + '02')

                    t.sleep(5)
                    if lock.arm == '10':
                        self.LockUp(lock.addr)
                        t.sleep(5)
                    if lock.arm == '10':
                        self.LockUp(lock.addr)
                        t.sleep(5)

                    if lock.arm == '01':
                        lock.carLeave = datetime.now()
                        lock.reservd2 = datetime.strftime(lock.carLeave, '%Y-%m-%d %H:%M:%S')
                        lock.carStayTime = (str(lock.carLeave - lock.carCome).split('.'))[0]
                        lock.reservd3 = lock.carStayTime
                        self.signal_Lock.emit(lock)
                        t.sleep(0.05)
                    else:  # 连续多次未判断到升锁到位，认为出现故障
                        lock.machine = '88'
                        pass

            if lock.arm == '01' or lock.arm == '00':
                lock.nocaron = 0
        pass

    def WaitCarStatusDisable(self):
        for lock in SharedMemory.LockList:
            if lock.waitcar == True:
                lock.waitcartime += 1

            if lock.carFinallyLeave == False:
                lock.waitcartime2 += 1

            if lock.waitcartime >= self.WaitCarComeTime:
                lock.waitcar = False
                lock.waitcartime = 0

            if lock.waitcartime2 >= self.WaitCarLeaveTime:
                lock.carFinallyLeave = True
                lock.waitcartime2 = 0
        pass


    def run(self):
        MyLog.debug("CanServer run ")
        self.ThreadTag = True

        t = threading.Thread(target=ServerOn,args=(self.spi,self))
        t.start()



    def LockUp(self, addr):
        buf = [int(addr[0:2],16),int(addr[2:4],16),int(addr[4:6],16),int(addr[6:8],16),2]
        self.mcp2515_write(buf)
        MyLog.info("LockUp"+addr)


    def LockDown(self, addr):
        buf = [int(addr[0:2],16),int(addr[2:4],16),int(addr[4:6],16),int(addr[6:8],16),3]
        self.mcp2515_write(buf)
        MyLog.info('LockDown:' + addr)

        for lock in SharedMemory.LockList:
            if lock.addr == addr:
                lock.waitcar = True
                lock.waitcartime = 0
                lock.waitcartime2 = 0

                lock.carCome = datetime.now()
                lock.reservd1 = datetime.strftime(lock.carCome,'%Y-%m-%d %H:%M:%S')
                lock.reservd2 = ''
                lock.reservd3 = ''
                lock.carFinallyLeave = False
                self.signal_Lock.emit(lock)




    def LockCMDExcute(self, str):
        MyLog.debug("触发Lockcmdexcute")
        if len(str) == 10:
            addr = str[0:8]
            cmd = str[8:10]
            if cmd == '02':
                self.LockUp(addr)
            elif cmd == '03':
                self.LockDown(addr)
            else:
                # to do other things here
                pass
        else:
            MyLog.error("FrontServer-->Lock的控制指令长度不正确")
            pass

    def LockCMDExcute2(self, str):
        MyLog.debug("触发Lockcmdexcute2 本地点击")
        if len(str) == 10:
            addr = str[0:8]
            cmd = str[8:10]
            if cmd == '02':
                self.LockUp(addr)
            elif cmd == '03':
                self.LockDown(addr)
            elif cmd == '04':
                buf = [int(addr[0:2], 16), int(addr[2:4], 16), int(addr[4:6], 16), int(addr[6:8], 16), 4]
                self.mcp2515_write(buf)
                MyLog.info("EnableAlarm" + addr)
            elif cmd == '05':
                buf = [int(addr[0:2], 16), int(addr[2:4], 16), int(addr[4:6], 16), int(addr[6:8], 16), 5]
                self.mcp2515_write(buf)
                MyLog.info("DisableAlarm" + addr)
            elif cmd == '06':
                buf = [int(addr[0:2], 16), int(addr[2:4], 16), int(addr[4:6], 16), int(addr[6:8], 16), 6]
                self.mcp2515_write(buf)
                MyLog.info("LockReset" + addr)

            else:
                # to do other things here
                pass
        else:
            MyLog.error("FrontServer-->Lock的控制指令长度不正确")
            pass


def ServerOn(SPI,self):
    MyLog.info('CanServer On through SPI Port!!')
    while self.ThreadTag:

        data = self.mcp2515_read()
        if data!=None and len(data)>0:
            tempstr = ''
            for i in range(0,len(data)):
                #tempstr +=hex(data[i])[2:].zfill(2)+' '
                tempstr += hex(data[i])[2:].zfill(2)
            print(tempstr)

            pos = tempstr.find('1823fafd')
            if pos==-1:
                print("收到数据不包含header")
            else:
                print(pos)
                tempstr = tempstr[pos+8:]
                strid = tempstr[0:8]

                print(stridList)
                if strid not in stridList:
                    stridList.append(strid)
                    print('Not in the list and Add on')

                    newLock = MyLock()
                    newLock.addr = tempstr[0:8]

                    # newLock.reservd1 = str_back[8:10]
                    # newLock.reservd2 = str_back[10:12]
                    # newLock.reservd3 = str_back[12:14]

                    tempstatus = bin(int(tempstr[8:10], 16))[2:].zfill(8)
                    newLock.arm = tempstatus[-4:-2]

                    newLock.car = tempstr[10:12]
                    # newLock.battery = str_back[20:22]
                    newLock.reservd4 = tempstr[12:14]
                    newLock.sensor = tempstr[14:16]
                    newLock.machine = tempstr[14:16]

                    SharedMemory.LockList.append(newLock)
                    self.signal_newLock.emit(newLock)
                    MyLog.info('New lock detected!')
                else:
                    # print('Already in the list')
                    for lock in SharedMemory.LockList:
                        if lock.addr == strid:

                            tempstatus = bin(int(tempstr[8:10], 16))[2:].zfill(8)
                            print(tempstatus)
                            if lock.arm != tempstatus[-4:-2]:
                                lock.arm = tempstatus[-4:-2]
                                lock.StatusChanged = True

                            if lock.car != tempstr[10:12]:
                                lock.car = tempstr[10:12]
                                lock.StatusChanged = True

                            if lock.reservd4 != tempstr[12:14]:
                                lock.reservd4 = tempstr[12:14]
                                lock.StatusChanged = True

                            if lock.sensor != tempstr[14:16]:
                                lock.sensor = tempstr[14:16]
                                lock.StatusChanged = True

                            if lock.machine != tempstr[14:16]:
                                lock.machine = tempstr[14:16]
                                lock.StatusChanged = True

                            self.signal_Lock.emit(lock)

        t.sleep(0.1)