import http.client
import time
import threading
import urllib.parse

conn =http.client.HTTPConnection("115.29.198.207:80",timeout=10)

EPDUStr = 'eb9004ff006400'  # 'eb90'+地址+状态+电量+异常代码+'AAAA09d7'
SendToWebstr = '/devices/connect/1ACF' + '沪A0108' + '01' + EPDUStr
conn.request("POST", urllib.parse.quote(SendToWebstr))
data1 = ''
try:
    r1 = conn.getresponse()
    print(r1)
    data1 = r1.read()
    data1 = str(data1, 'utf-8')
    print('RecvFrServer:' + data1)

    if data1 == '':
        print('未收到服务器回复！')
        pass
    else:
        print(data1)
except Exception as ex2:
    print(ex2)