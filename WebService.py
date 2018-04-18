import codecs
import http.client
import time
import threading
from Data import MyLock
from Data import SharedMemory
from PyQt5 import QtCore
from PyQt5.QtCore import *
import urllib.parse
import logging.config
from os import path
import os
from gpioctr import GpioCtr


MyLog2 = logging.getLogger('ws_debug_log2')       #log data
MajorLog = logging.getLogger('ws_error_log')      #log error

class WebServer(QThread):
    signal = pyqtSignal(str)
    def __init__(self):
        super(WebServer,self).__init__()
        MyLog2.debug('WebService in')

        self.lostcount = 0
        self.rebootwait = 0
        self.rebootRasp = 0

        try:
            with open(file=path.expandvars('$HOME') + '/Downloads/WWTFrontServer_SPI/FrontServerID', mode='r') as file:
                self.StrID = file.read()
        except Exception as ex:
            MajorLog(ex+'From openfile frontserverid')
            self.StrID = '沪A0908'
        MyLog2.debug(self.StrID)

        global conn
        conn =http.client.HTTPConnection("115.29.198.207:80",timeout=10)
       # conn = http.client.HTTPConnection("http://weiweitong.daoyintech.com")
        self.FrontRebootTag = 10
        self.ThreadTag = True
        t = threading.Thread(target=ServerOn, args=(conn, self))
        t.start()
        self.mtimer = QTimer()
        self.mtimer.timeout.connect(self.SendAllLock2Server)
        self.mtimer.start(60000)


    def close(self):
        self.ThreadTag = False

    def run(self):
        MyLog2.debug("WebServer run again try reconnect1")
        self.ThreadTag = True
        conn =http.client.HTTPConnection("115.29.198.207:80",timeout=10)
        t = threading.Thread(target=ServerOn, args=(conn, self))
        t.start()

    def SendAllLock2Server(self):
        for lock in SharedMemory.LockList:
            lock.StatusChanged = True


def ServerOn(conn,self):
    time.sleep(3)
    MyLog2.info('WebService ServerOn thread on')
    while self.ThreadTag:
        MyLog2.debug('Requesting!')

        EPDUStr =''
        EPDUNums = 0                    #实际发送的EPDU个数

        if self.FrontRebootTag>0:
            self.FrontRebootTag = self.FrontRebootTag - 1
            for item in SharedMemory.LockList:
                item.StatusChanged = True
            pass

        for item in SharedMemory.LockList:
            if item.StatusChanged:
                EPDUNums = EPDUNums +1
                item.StatusChanged = False
                status = 'ff'           #检测摇臂状态，根据与后台的协议转化为Web发送的值

                if item.arm =='10':     #摇臂降下到位
                    status = '20'
                elif item.arm =='01':   #摇臂升起到位
                    status = '10'
                elif item.arm =='00':   #摇臂正在升降
                    status = '00'
                else:
                    status = 'FF'

                ErrCodeValue = 0
                if item.sensor == '55':#地磁故障
                    ErrCodeValue +=1
                if item.sensor == '11':#探头1故障
                    ErrCodeValue +=2
                if item.sensor == '22':#探头2故障
                    ErrCodeValue +=4
                if item.sensor == '33':#两个探头都故障
                    ErrCodeValue +=6

                if item.machine == '55':#摇臂遇阻
                    ErrCodeValue += 16
                if item.machine == 'FF':#摇臂破坏
                    ErrCodeValue += 32
                if item.machine == '88':#电机连轴故障
                    ErrCodeValue += 64

                item.ErrorCode = hex(ErrCodeValue)[2:].zfill(2)     #将摇臂故障根据协议转化为发给Web的值

                EPDUStr +='eb90'+item.addr +status+item.car+item.battery+item.ErrorCode      #'eb90'+地址+状态+电量+异常代码+'AAAA09d7'
                pass
        SendToWebstr = '/devices/connect/1ACF'+self.StrID + str(EPDUNums).zfill(2)+EPDUStr
        MyLog2.info('SendToServer:'+SendToWebstr)
        try:
            conn.request("POST",urllib.parse.quote(SendToWebstr))

        except Exception as ex1:
            MajorLog.error('Error From conn.requeset Post Failed')
            #是否在这里添加，如果多次Post失败则进入休眠等待N分钟后再重新连接
            self.lostcount +=1
            MajorLog.error("Exception lostcount=:" + str(self.lostcount))
            if self.lostcount > 3:
                MajorLog.error("Try Reconnect To Server:" + str(self.rebootwait))
                conn = http.client.HTTPConnection("115.29.198.207:80", timeout=10)
                time.sleep(10)
                self.lostcount = 0
                self.rebootwait +=1

                if self.rebootwait > 30:
                    self.rebootwait = 0
                    MajorLog.error('Reboot 4G Now!!')

                    GpioCtr.Route4GReboot(self)#reboot 4G路由器之后需要重新开启连接服务，否则一直异常
                    time.sleep(2)
                    self.rebootRasp +=1

                if self.rebootRasp >=1:#这里采用重启4G路由器后直接重启树莓派的方法，后续可以改为重启4G路由器后重启WebService的方法
                    MajorLog.error('After Reboot 4G Reboot Raspberry Now!!')
                    time.sleep(2)
                    os.system('reboot')
            continue
        finally:
            pass

        data1 = ''
        try:
            r1 = conn.getresponse()
            data1 = r1.read()
            data1 = str(data1, 'utf-8')
            MyLog2.info('RecvFrServer:' + data1)

            if data1 == '':
                MyLog2.error('未收到服务器回复！')
                pass
            elif data1 == 'Heart':
                self.rebootwait = 0 #收到心跳则将rebootwait计数重置为0
                pass
            else:
                if len(data1) >= 10:
                    if data1[0:4] == 'eb90' and len(data1)==10:      #获取全部锁状态、开关电源、重启现场、获取日志、获取数据
                        cmdtype = data1[6:8]
                        cmd = data1[8:10]

                        if cmdtype == '01' and cmd == '01':
                            for lock in SharedMemory.LockList:
                                lock.StatusChanged = True

                        if cmdtype == '01' and cmd == '13':  # 现场日志
                            pass
                        if cmdtype == '01' and cmd == '14':  # 现场数据
                            pass
                        if cmdtype == '02' and cmd == '10':  # 打开锁电源
                            GpioCtr.LockPowerOn(self)
                            pass
                        if cmdtype == '02' and cmd == '11':  # 关闭锁电源
                            GpioCtr.LockPowerOff(self)
                            pass
                        if cmdtype == '03' and cmd == '12':  # 重启树莓派
                            os.system('reboot')
                            pass

                    if data1[0:4] == 'eb90' and data1[4:6]!='00':
                        cmdlist = data1[4:len(data1)].split(';')
             #           MyLog2.debug(cmdlist)
             #           MyLog2.debug(len(cmdlist))
                        for i in range(len(cmdlist)):
                            temp = cmdlist[i]
              #              MyLog2.debug('cmdlist='+temp)

                            addr = temp[0:2]
                            cmdtype = temp[2:4]
                            cmd = temp[4:6]

                            strToserial = ''  # 控制指令
                            if cmd == '03':
                                strToserial += '03'
                            if cmd == '04':
                                strToserial += '04'
                            if cmd == '05':
                                strToserial += '05'
                            if cmd == '06':
                                strToserial += '06'
                            if cmd == '07':
                                strToserial += '07'
                            if cmd == '08':
                                strToserial += '08'
                            if cmd == '09':
                                strToserial += '09'
                            strToserial += addr
                            MyLog2.info("触发" + strToserial)
                            self.signal.emit(strToserial)

        except Exception as ex2:
            MyLog2.error('From conn.getresponse:')
            MyLog2.error(ex2)
            MajorLog.error('From conn.getresponse:')
            MajorLog.error(ex2)
        finally:
            pass

        time.sleep(2)
    MyLog2.info("WebService Server Thread off!")
    conn.close()