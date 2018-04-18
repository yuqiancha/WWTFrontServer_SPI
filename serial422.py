import crcmod.predefined
import binascii
import os
from binascii import unhexlify
from binascii import hexlify
import serial.tools.list_ports
import time as t
from datetime import *
import threading
import serial
from Data import MyLock
from Data import SharedMemory
from os import path
from PyQt5 import QtCore
from PyQt5.QtCore import *
import logging
import configparser

MyLog = logging.getLogger('ws_debug_log')       #log data
MajorLog = logging.getLogger('ws_error_log')      #log error

class RS422Func(QThread):
    signal_newLock = pyqtSignal(MyLock)
    signal_Lock = pyqtSignal(MyLock)

    def __init__(self):
        super(RS422Func, self).__init__()
        MyLog.info('Rs422Func init')
        MyLog.info('Rs422Func init')

        self.WaitCarComeTime = int(120)              #等待车子停进来的时间，2min不来就升锁
        self.WaitCarLeaveTime = int(300)             #车子停进来前5min，依旧是2min升锁，超出时间立刻升锁
        self.AfterCarLeaveTime = int(10)             #超出5min，认为车子是要走了，1min升锁

        try:
            cf = configparser.ConfigParser()
            cf.read(path.expandvars('$HOME') + '/WWTFrontServer_Can/Configuration.ini',encoding="utf-8-sig")

            self.WaitCarComeTime = cf.getint("StartLoad","WaitCarComeTime")
            self.WaitCarLeaveTime = cf.getint("StartLoad","WaitCarLeaveTime")
            self.AfterCarLeaveTime = cf.getint("StartLoad","AfterCarLeaveTime")
        except Exception as ex:
            MajorLog(ex+'From openfile /waitcartime')

        MyLog.debug("WaitCarComeTime:"+str(self.WaitCarComeTime))
        MyLog.debug("WaitCarLeaveTime:"+str(self.WaitCarLeaveTime))
        MyLog.debug("AfterCarLeaveTime:" + str(self.AfterCarLeaveTime))

        self.myEvent = threading.Event()
        self.mutex = threading.Lock()
        self.scanTag = False

        self.ThreadTag = True
#        global LockList
#        LockList = []
        global stridList
        stridList = []
        global crc16_xmode
        crc16_xmode = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xffff, xorOut=0x0000)

        self.mtimer = QTimer()
        self.mtimer.timeout.connect(self.LockAutoDown)
        self.mtimer.start(1000)

        self.mtimer2 = QTimer()
        self.mtimer2.timeout.connect(self.WaitCarStatusDisable)
        self.mtimer2.start(1000)
        pass


    def LockAutoDown(self):#定时器调用，检测无车满60s后自动发送升锁指令
        for lock in SharedMemory.LockList:
            if lock.arm == 'ff':
                if lock.car == '00':
                    lock.nocaron += 1
                else:
                    lock.nocaron = 0

                if lock.nocaron >= self.WaitCarComeTime and lock.waitcar == False:  #降锁后等待车子来停
                    lock.nocaron = 0
                    self.LockUp(lock.addr)
                    lock.carLeave = datetime.now()
                    lock.reservd2 = datetime.strftime(lock.carLeave, '%Y-%m-%d %H:%M:%S')
                    lock.carStayTime = (str(lock.carLeave - lock.carCome).split('.'))[0]
                    lock.reservd3 = lock.carStayTime
                    self.signal_Lock.emit(lock)
                    t.sleep(0.05)

                if lock.nocaron>=self.AfterCarLeaveTime and lock.carFinallyLeave==True:                        #车子离开等待60s就升锁
                    lock.carFinallyLeave = True
                    lock.nocaron = 0

                    self.LockUp(lock.addr)
                    t.sleep(5)
                    if lock.arm =='ff':
                        self.LockUp(lock.addr)
                        t.sleep(5)
                    if lock.arm =='ff':
                        self.LockUp(lock.addr)
                        t.sleep(5)

                    if lock.arm =='55':
                        lock.carLeave = datetime.now()
                        lock.reservd2 = datetime.strftime(lock.carLeave, '%Y-%m-%d %H:%M:%S')
                        lock.carStayTime = (str(lock.carLeave - lock.carCome).split('.'))[0]
                        lock.reservd3 = lock.carStayTime
                        self.signal_Lock.emit(lock)
                        t.sleep(0.05)
                    else:#连续多次未判断到升锁到位，认为出现故障
                        lock.machine = '88'
                        pass

            if lock.arm == '55' or lock.arm =='00':
                lock.nocaron = 0
        pass

    def WaitCarStatusDisable(self):
        for lock in SharedMemory.LockList:
            if lock.waitcar == True:
                lock.waitcartime +=1

            if lock.carFinallyLeave == False:
                lock.waitcartime2 +=1

            if lock.waitcartime >= self.WaitCarComeTime:
                lock.waitcar =False
                lock.waitcartime =0

            if lock.waitcartime2 >= self.WaitCarLeaveTime:
                lock.carFinallyLeave = True
                lock.waitcartime2 = 0
        pass

    def ScanPort(self):
        global ser
        MyLog.info("Enter ScanPort")
        MajorLog.info("Enter ScanPort")
        SharedMemory.LockList=[]
        stridList.clear()
        try:
            ser = serial.Serial('/dev/ttyAMA0', 9600, timeout=0.1)
            if ser.isOpen():
                t = threading.Thread(target=InitPortList, args=(ser, self))
                t.start()
                t2 = threading.Thread(target=Normalchaxun, args=(ser, self))
                t2.start()
        except Exception as ex:
            MajorLog.error(ex)
            MyLog.error(ex)
            try:
                ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=0.1)
                if ser.isOpen():
                    t = threading.Thread(target=InitPortList, args=(ser, self))
                    t.start()
                    t2 = threading.Thread(target=Normalchaxun, args=(ser, self))
                    t2.start()
            except Exception as ex:
                MajorLog.error(ex)
                MyLog.error(ex)

    def ChaXun(self,str):
        Address = str
        Tempstr = (Address + '0420010004').replace('\t', '').replace(' ', '').replace('\n', '').strip()
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
 #       print('ChaXun:'+SendStr)
        self.WriteToPort(SendStr)
        data = recv(ser, self)


    def LockCMDExcute(self, str):
        MyLog.debug("触发Lockcmdexcute")
        if len(str) == 4:
            if str[0:2] == '03':
                self.LockReset(str[2:4])
            elif str[0:2] == '04':
                self.LockUp(str[2:4])
            elif str[0:2] == '05':
                self.LockDown(str[2:4])
            elif str[0:2] == '06':
                self.LockDownAndRest(str[2:4])
            elif str[0:2] == '07':
                self.LedOn(str[2:4])
            elif str[0:2] == '17':
                self.LedOff(str[2:4])
            elif str[0:2] == '08':
                self.EnableAlarm(str[2:4])
            elif str[0:2] == '09':
                self.DisableAlarm(str[2:4])
            elif str[0:2] == 'F1':
                self.ChaoShengTest(str[2:4])
            elif str[0:2] == 'F4':
                self.QuitTest(str[2:4])
            else:
                # to do other things here
                pass
        else:
            MyLog.error("FrontServer-->Lock的控制指令长度不正确")
            pass

            # eb 90 08 01 05 10 02 FF 00 29 3A


    def ChaoShengTest(self, str):
        Address = str
        Tempstr = Address + '0601050300'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LockReset:' + SendStr)

        self.WriteToPort(SendStr)

    def QuitTest(self, str):
        Address = str
        Tempstr = Address + '0601050000'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LockReset:' + SendStr)

        self.WriteToPort(SendStr)


    def LockReset(self, str):
        Address = str
        Tempstr = Address + '051001FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LockReset:' + SendStr)

        self.WriteToPort(SendStr)

    def LockUp(self, str):
        Address = str
        Tempstr = Address + '051002FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LockUp:' + SendStr)
        self.WriteToPort(SendStr)


    def LockDown(self, str):
        Address = str
        Tempstr = Address + '051003FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LockDown:' + SendStr)
        self.WriteToPort(SendStr)
        for lock in SharedMemory.LockList:
            if lock.addr == Address:
                lock.waitcar = True

                lock.waitcartime = 0
                lock.waitcartime2 = 0

                lock.carCome = datetime.now()
                lock.reservd1 = datetime.strftime(lock.carCome,'%Y-%m-%d %H:%M:%S')
                lock.reservd2 = ''
                lock.reservd3 = ''

                lock.carFinallyLeave = False

                self.signal_Lock.emit(lock)

    def LockDownAndRest(self,str):
        Address = str
        Tempstr = Address + '051006FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LockDownAndRest:' + SendStr)
        self.WriteToPort(SendStr)

    def LedOn(self,str):
        Address = str
        Tempstr = Address + '051008FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LedOn:' + SendStr)
        self.WriteToPort(SendStr)


    def LedOff(self,str):
        Address = str
        Tempstr = Address + '051009FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('LedOff:' + SendStr)
        self.WriteToPort(SendStr)

    def EnableAlarm(self, str):
        Address = str
        Tempstr = Address + '051004FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('EnableAlarm:' + SendStr)
        self.WriteToPort(SendStr)

    def DisableAlarm(self, str):
        Address = str
        Tempstr = Address + '051005FF00'
        strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
        SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
        MyLog.debug('DisableAlarm:' + SendStr)
        self.WriteToPort(SendStr)

    def WriteToPort(self,SendStr):
 #       MyLog.info('SendToLock:' + SendStr)
        try:
            if ser.isOpen():
                self.mutex.acquire()
                d = bytes.fromhex(SendStr)
                ser.write(d)
                t.sleep(0.05)
                self.mutex.release()
        except Exception as ex4:
            print(ex4)
            print('Error from WriteToPort')
        pass


def InitPortList(ser,self):
    MyLog.info('Enter InitPortList')
    ScanMaxLock = 0x1f
    if ser.isOpen():
        count = 0
        while count < ScanMaxLock:
            Address = hex(count)[2:].zfill(2)
            Tempstr = (Address + '0420010004').replace('\t', '').replace(' ', '').replace('\n', '').strip()
            count += 1

            strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
            SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
            d = bytes.fromhex(SendStr)
            ser.write(d)
            t.sleep(0.1)
            try:
                data = recv(ser,self)
            except Exception as ex:
                MyLog.error(ex)
        MyLog.debug(SharedMemory.LockList)

        count = 0
        while count < ScanMaxLock:
            Address = hex(count)[2:].zfill(2)
            Tempstr = (Address + '0420010004').replace('\t', '').replace(' ', '').replace('\n', '').strip()
            count += 1

            strcrc = hex(crc16_xmode(unhexlify(Tempstr)))[2:].zfill(4)
            SendStr = 'eb9008' + Tempstr + strcrc[2:4] + strcrc[0:2]
            d = bytes.fromhex(SendStr)
            ser.write(d)
            t.sleep(0.1)
            try:
                data = recv(ser, self)
            except Exception as ex:
                MyLog.error(ex)
        MyLog.debug(SharedMemory.LockList)

        self.scanTag = True
    else:
        MyLog.error('/dev/ttyAMA0 can not find!')


def Normalchaxun(serial,self):
    while self.scanTag==False:
        continue
    MyLog.info("ScanPortList Finished!")

    while self.ThreadTag:                                   #Main Loop is here!
        if serial.isOpen():
#            if self.myEvent.wait(0.1):
#                t.sleep(0.1)
#                print('sleep 100ms')

            if len(SharedMemory.LockList)>0:
                for lock in SharedMemory.LockList:
                    self.ChaXun(lock.addr)
                    t.sleep(0.05)                           #50ms等待时间，防止查询太快导致485紊乱，在Write和Recv中已有50ms延迟，此处可以省略
            else:
                MyLog.error('No Lock in the list from serial422.py Normalchaxun')
            t.sleep(1)                                      #轮训间隔，每间隔N秒进行一次轮训获取连接车位锁的状态
    pass

def recv(serial,self):
    global data
    while self.ThreadTag:
        try:
            self.mutex.acquire()
            data = serial.read(30)
            t.sleep(0.05)
            self.mutex.release()
        except Exception as ex3:
            MyLog.error(ex3+'from serial422.py recv')
            pass
        if data =='':
            continue
        else:
        #    print(data)
            str_back = str(hexlify(data), "utf-8")
     #       MyLog.debug('RecvFromLock:' + str_back)
            if len(str_back)==32:
                if str_back[0:6]=='eb900d':
                    strid = str_back[6:8]
                    MyLog.info('RecvFromLock:' + str_back)
                    print(stridList)
                    if strid not in stridList:
                        stridList.append(strid)
                        #print('Not in the list and Add on')
                        newLock=MyLock()
                        newLock.addr =str_back[6:8]
#                        newLock.reservd1 = str_back[8:10]
#                        newLock.reservd2 = str_back[10:12]
#                        newLock.reservd3 = str_back[12:14]
                        newLock.reservd1 = ''
                        newLock.reservd2 = ''
                        newLock.reservd3 = ''
                        newLock.mode =str_back[14:16]
                        newLock.arm = str_back[16:18]
                        newLock.car = str_back[18:20]
                        newLock.battery = str_back[20:22]
                        newLock.reservd4 = str_back[22:24]
                        newLock.sensor = str_back[24:26]
                        newLock.machine = str_back[26:28]
                        newLock.crcH=str_back[28:30]
                        newLock.crcL=str_back[30:32]
                        SharedMemory.LockList.append(newLock)
                        self.signal_newLock.emit(newLock)
                        MyLog.info('New lock detected!')
                    else:
                        #print('Already in the list')
                        for lock in SharedMemory.LockList:
                            if lock.addr == strid:
                         #       if lock.reservd1 != str_back[8:10]:
                         #           lock.reservd1 = str_back[8:10]
                         #           lock.StatusChanged = True

                         #       if lock.reservd2 != str_back[10:12]:
                         #           lock.reservd2 = str_back[10:12]
                         #           lock.StatusChanged = True

                         #       if lock.reservd3 != str_back[12:14]:
                         #           lock.reservd3 = str_back[12:14]
                         #           lock.StatusChanged = True;
                                if lock.mode != str_back[14:16]:
                                    lock.mode = str_back[14:16]
                                    lock.StatusChanged = True

                                if lock.arm != str_back[16:18]:
                                    lock.arm = str_back[16:18]
                                    lock.StatusChanged = True

                                if lock.car != str_back[18:20]:
                                    lock.car = str_back[18:20]
                                    lock.StatusChanged = True

                                if lock.battery != str_back[20:22]:
                                    lock.battery = str_back[20:22]
                                    lock.StatusChanged = True

                                if lock.reservd4 != str_back[22:24]:
                                    lock.reservd4 = str_back[22:24]
                                    lock.StatusChanged = True

                                if lock.sensor != str_back[24:26]:
                                    lock.sensor = str_back[24:26]
                                    lock.StatusChanged = True


                                if lock.machine != str_back[26:28]:
                                    lock.machine = str_back[26:28]
                                    lock.StatusChanged = True

                                lock.crcH = str_back[28:30]
                                lock.crcL = str_back[30:32]

#                                if lock.StatusChanged:
#                                    MyLog.info('RecvFromLock:' + str_back)

                                self.signal_Lock.emit(lock)
            break
        t.sleep(0.05)

    return data
