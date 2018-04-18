
#查询回复eb 90 0d 01 04 08 00 ff 55 00 64 00 00 00 38 37
class MyLock(object):
    def __init__(self):
        self.addr = ''
        self.reservd1 = '04'
        self.reservd2 = '08'
        self.reservd3 = '00'

        self.arm = '55'
        self.car ='00'
        self.battery ='64'
        self.reservd4 = '00'
        self.sensor = '00'
        self.machine ='00'

        self.ErrorCode ='00'
        self.StatusChanged = False              #锁的状态是否有改变

        self.nocaron = 0                        #检测是否有车，无车超过一定时间自动升锁
        self.waitcar = False                    #判断 True表示 2分钟内收到降锁指令，等待车辆停靠 False表示2分钟内没收到降锁指令
        self.waitcartime = 0                    #判断等待车辆停靠时间
        self.waitcartime2 = 0                   #车辆降锁2分钟内认为车子在反复倒车，不升锁
        self.carFinallyLeave = False                   #判断是否是车子离开的情况，如果车子离开，立刻升锁



        self.carCome = 0                        #车来时间
        self.carLeave = 0                       #车走时间
        self.carStayTime = 0                    #车停靠时间
        self.money = 0

class SharedMemory(object):
    LockList = []