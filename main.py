import sys
import serial
from PyQt5 import QtCore
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import binascii
import serial.tools.list_ports
from Ui_Form import Ui_Form
from serial422 import RS422Func
from Data import MyLock
from WebService import WebServer
from CanServer import CanServer
import time
import logging
import logging.config
from gpioctr import GpioCtr
from os import path
import os
import subprocess

log_file_path = path.join(path.dirname(path.abspath(__file__)), 'logging.config')
logging.config.fileConfig(log_file_path)
MyLog = logging.getLogger('ws_debug_log')         #log data
MyLog2 = logging.getLogger('ws_debug_log2')       #log net data
MajorLog = logging.getLogger('ws_error_log')      #log error


class Main(QWidget,Ui_Form):
    signal_LockCMD = pyqtSignal(str)

    def __init__(self):
        super(Main,self).__init__()
        self.setupUi(self)
        self.init()

    def init(self):
        self.handlAllTag = False
        self.tableWidget.setColumnCount(10)
        self.tableWidget.setRowCount(0)
        header = []
        header.append('锁地址')
        header.append('降锁时刻')
        header.append('升锁时刻')
        header.append('停车时间')

        header.append('摇臂状态')
        header.append('车检状态')
        header.append('电量')
        header.append('Reserved')
        header.append('传感故障')
        header.append('机构故障')

        self.tableWidget.setHorizontalHeaderLabels(header)

        self.pushButton_Reset.clicked.connect(self.btnResetClicked)
        self.pushButton_LockUp.clicked.connect(self.btnLockUpClicked)
        self.pushButton_LockDown.clicked.connect(self.btnLockDownClicked)
        self.pushButton_LockDownRest.clicked.connect(self.btnLockDownAndRestClicked)
        self.pushButton_LightOn.clicked.connect(self.btnLedOnClicked)
        self.pushButton_LightOff.clicked.connect(self.btnLedOffClicked)
        self.pushButton_EnableAlarm.clicked.connect(self.btnEnableAlarmClicked)
        self.pushButton_DisableAlarm.clicked.connect(self.btnDisableAlarmClicked)
        self.pushButton_LockPowerOn.clicked.connect(self.btnLPowerOnClicked)
        self.pushButton_LockPowerOff.clicked.connect(self.btnPowerOffClicked)
        self.pushButton_webstatus.clicked.connect(self.webstatusClicked)
        self.pushButton_exit.clicked.connect(self.btnExitClicked)
        self.pushButton_exit.clicked.connect(self.formcloseClicked)
        self.pushButton_4GReboot.clicked.connect(self.btn4GRebootClicked)
        self.tableWidget.clicked.connect(self.tableWidgetClicked)
        self.pushButton_ChaoShengTest.clicked.connect(self.btnChaoShengTestClicked)
        self.pushButton_QuitTest.clicked.connect(self.btnQuitTestClicked)
        self.pushButton_handleAll.clicked.connect(self.btnHandleAllClicked)
        self.pushButton_CanServer.clicked.connect(self.CanServerClicked)
        self.pushButton_CanServer.isVisible= False;

        pass

    def CanServerClicked(self):
        if self.pushButton_CanServer.text()=='启动CanServer':
            self.pushButton_CanServer.setText('关闭CanServer')
            MyLog.info("界面启动Canserver")
            canservice.run()
            time.sleep(1)
            subprocess.Popen('./CanClient')

        else:
            MyLog.info("界面关闭Canserver")
            self.pushButton_CanServer.setText('启动CanServer')
            canservice.CanServerClose()


    def btnHandleAllClicked(self):
        if self.pushButton_handleAll.text() == '切换统一操作':
            self.pushButton_handleAll.setText('切换单独操作')
            self.handlAllTag = True
        else:
            self.pushButton_handleAll.setText('切换统一操作')
            self.handlAllTag = False

        pass

    def tableWidgetClicked(self):
        row = self.tableWidget.currentRow()
        addr = self.tableWidget.item(row,0).text()
        self.comboBox.setCurrentText(addr)
        pass

    def btn4GRebootClicked(self):
        gpio.Route4GReboot()

        pass

    def btnExitClicked(self):
        canservice.ThreadTag = False
        webservice.mtimer.stop()
        canservice.mtimer.stop()
        canservice.mtimer2.stop()

        pass

    def btnResetClicked(self):
        addr = self.comboBox.currentText()
        cmd = '03'
        self.signal_LockCMD.emit(cmd+addr)
        pass

    def btnLockUpClicked(self):
        if self.handlAllTag==False:
            addr = self.comboBox.currentText()
            cmd = '02'
            self.signal_LockCMD.emit(addr + cmd)
        else:
            row_count = self.tableWidget.rowCount()
            for row_index in range(row_count):
                addr = self.tableWidget.item(row_index, 0).text()
                cmd = '02'
                self.signal_LockCMD.emit(addr+cmd)
                time.sleep(1)
        pass

    def btnLockDownClicked(self):
        if self.handlAllTag==False:
            addr = self.comboBox.currentText()
            cmd = '03'
            self.signal_LockCMD.emit(addr + cmd)
        else:
            row_count = self.tableWidget.rowCount()
            for row_index in range(row_count):
                addr = self.tableWidget.item(row_index, 0).text()
                cmd = '03'
                self.signal_LockCMD.emit(addr+cmd)
                time.sleep(1)
        pass

    def btnLockDownAndRestClicked(self):
        if self.handlAllTag==False:
            addr = self.comboBox.currentText()
            cmd = '06'
            self.signal_LockCMD.emit(addr + cmd)
        else:
            row_count = self.tableWidget.rowCount()
            for row_index in range(row_count):
                addr = self.tableWidget.item(row_index, 0).text()
                cmd = '06'
                self.signal_LockCMD.emit(addr+cmd)
                time.sleep(1)
        pass

    def btnLedOnClicked(self):
        addr = self.comboBox.currentText()
        cmd = '07'
        self.signal_LockCMD.emit(cmd+addr)
        pass

    #Test LED OFF,Did not show in the protocol
    def btnLedOffClicked(self):
        addr = self.comboBox.currentText()
        cmd = '17'
        self.signal_LockCMD.emit(cmd+addr)
        pass

    def btnEnableAlarmClicked(self):
        if self.handlAllTag==False:
            addr = self.comboBox.currentText()
            cmd = '04'
            self.signal_LockCMD.emit(addr + cmd)
        else:
            row_count = self.tableWidget.rowCount()
            for row_index in range(row_count):
                addr = self.tableWidget.item(row_index, 0).text()
                cmd = '04'
                self.signal_LockCMD.emit(addr+cmd)
                time.sleep(1)
        pass

    def btnDisableAlarmClicked(self):
        if self.handlAllTag==False:
            addr = self.comboBox.currentText()
            cmd = '05'
            self.signal_LockCMD.emit(addr + cmd)
        else:
            row_count = self.tableWidget.rowCount()
            for row_index in range(row_count):
                addr = self.tableWidget.item(row_index, 0).text()
                cmd = '05'
                self.signal_LockCMD.emit(addr+cmd)
                time.sleep(1)
        pass

    def btnChaoShengTestClicked(self):
        if self.handlAllTag==False:
            addr = self.comboBox.currentText()
            cmd = 'F1'
            self.signal_LockCMD.emit(cmd+addr)
        else:
            row_count = self.tableWidget.rowCount()
            for row_index in range(row_count):
                addr = self.tableWidget.item(row_index, 0).text()
                cmd = 'F1'
                self.signal_LockCMD.emit(cmd + addr)
                time.sleep(1)
        pass

    def btnQuitTestClicked(self):
        if self.handlAllTag==False:
            addr = self.comboBox.currentText()
            cmd = 'F4'
            self.signal_LockCMD.emit(cmd+addr)
        else:
            row_count = self.tableWidget.rowCount()
            for row_index in range(row_count):
                addr = self.tableWidget.item(row_index, 0).text()
                cmd = 'F4'
                self.signal_LockCMD.emit(cmd + addr)
                time.sleep(1)
        pass


    def btnLPowerOnClicked(self):
        gpio.LockPowerOn()
        pass

    def btnPowerOffClicked(self):
        gpio.LockPowerOff()
        pass


    def ShowNewLock(self,MyLock):
        row_count = self.tableWidget.rowCount();
        self.tableWidget.insertRow(row_count)
        self.comboBox.addItem(MyLock.addr)

        item0 = QTableWidgetItem(MyLock.addr)
        item1 = QTableWidgetItem(MyLock.reservd1)
        item2 = QTableWidgetItem(MyLock.reservd2)
        item3 = QTableWidgetItem(MyLock.reservd3)
        item4 = QTableWidgetItem(MyLock.arm)
        item5 = QTableWidgetItem(MyLock.car)
        item6 = QTableWidgetItem(MyLock.battery)
        item7 = QTableWidgetItem(MyLock.reservd4)
        item8 = QTableWidgetItem(MyLock.sensor)
        item9 = QTableWidgetItem(MyLock.machine)


        self.tableWidget.setItem(row_count,0,item0)
        self.tableWidget.setItem(row_count, 1, item1)
        self.tableWidget.setItem(row_count, 2, item2)
        self.tableWidget.setItem(row_count, 3, item3)
        self.tableWidget.setItem(row_count, 4, item4)
        self.tableWidget.setItem(row_count, 5, item5)
        self.tableWidget.setItem(row_count, 6, item6)
        self.tableWidget.setItem(row_count,7,item7)
        self.tableWidget.setItem(row_count, 8, item8)
        self.tableWidget.setItem(row_count, 9, item9)

        pass

    def ShowLock(self,MyLock):
        row_count = self.tableWidget.rowCount();
        for row_index in range(row_count):
            if self.tableWidget.item(row_index,0).text() == MyLock.addr:
                item0 = QTableWidgetItem(MyLock.addr)
                item1 = QTableWidgetItem(MyLock.reservd1)
                item2 = QTableWidgetItem(MyLock.reservd2)
                item3 = QTableWidgetItem(MyLock.reservd3)
            #    item1 = QTableWidgetItem(MyLock.carCome)
             #   item2 = QTableWidgetItem(MyLock.carLeave)
              #  item3 = QTableWidgetItem(MyLock.carStayTime)

                str_arm = '未知'
                if MyLock.arm=='01':
                    str_arm='升起'
                elif MyLock.arm=='10':
                    str_arm='降下'
                elif MyLock.arm=='00':
                    str_arm='升降中'
                else:
                    str_arm = MyLock.arm
                item4 = QTableWidgetItem(str_arm)

                str_car = '未知'
                if MyLock.car=='00':
                    str_car='无车'
                elif MyLock.car=='0f':
                    str_car='有车'
                elif MyLock.car =='05':
                    str_car='Unknown'
                else:
                    str_car = MyLock.car
                item5 = QTableWidgetItem(str_car)

                item6 = QTableWidgetItem(MyLock.battery)

                item7 = QTableWidgetItem(MyLock.reservd4)


                sensor = int(MyLock.sensor,16)
                str_sensor = ''
                if sensor & 0x01 == 0x01:#地磁故障
                    str_sensor +='地磁故障'
                if sensor & 0x02 == 0x02:#探头1故障
                    str_sensor +='探头1故障'
                if sensor & 0x04 == 0x04:#探头2故障
                    str_sensor +='探头2故障'
                if str_sensor=='':
                    str_sensor ='无故障'

                item8 = QTableWidgetItem(str_sensor)

                machine = int(MyLock.machine, 16)
                str_machine = ''
                if machine & 0x10 == 0x10:#摇臂遇阻
                    str_machine += '摇臂遇阻'
                if machine & 0x20 == 0x20:#摇臂破坏
                    str_machine += '摇臂超时'
                if machine & 0x40 == 0x40:#摇臂报警
                    str_machine += '摇臂报警'
                if str_machine=='':
                    str_machine ='无故障'
                item9 = QTableWidgetItem(str_machine)


                self.tableWidget.setItem(row_index, 0, item0)
                self.tableWidget.setItem(row_index, 1, item1)
                self.tableWidget.setItem(row_index, 2, item2)
                self.tableWidget.setItem(row_index, 3, item3)
                self.tableWidget.setItem(row_index, 4, item4)
                self.tableWidget.setItem(row_index, 5, item5)
                self.tableWidget.setItem(row_index, 6, item6)
                self.tableWidget.setItem(row_index, 7, item7)
                self.tableWidget.setItem(row_index, 8, item8)
                self.tableWidget.setItem(row_index, 9, item9)


        pass

    def webstatusClicked(self):
        print(self.pushButton_webstatus.text())
        if self.pushButton_webstatus.text() == 'WebServiceOn':
            self.pushButton_webstatus.setText('WebServiceOff')
            webservice.run()
        else:
            self.pushButton_webstatus.setText('WebServiceOn')
            webservice.close()
        pass

    def formcloseClicked(self):
        webservice.close()
        time.sleep(1)
        QCoreApplication.quit()
        pass

if __name__ == '__main__':
    app=QApplication(sys.argv)
    ex=Main()
    ex.show()

    gpio = GpioCtr()

    canservice = CanServer()
    canservice.run()

    webservice = WebServer()

    webservice.signal.connect(canservice.LockCMDExcute)

    ex.signal_LockCMD.connect(canservice.LockCMDExcute2)


    canservice.signal_Lock.connect(ex.ShowLock)
    canservice.signal_newLock.connect(ex.ShowNewLock)


    sys.exit(app.exec_())