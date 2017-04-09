#!/usr/bin/env python
# -*- coding: utf-8 -*-
#获得火币网最新价格，在系统托盘内显示并更新
#作者: 师访, 中国科学技术大学(2017-02-25)

import os
import sys
import subprocess
import urllib2
import json
from threading import Timer
import time
from time import strftime,gmtime
import wx
import numpy as np
from wx.lib.plot import PlotCanvas, PlotGraphics, PolyLine, PolyMarker
from matplotlib.figure import Figure  
import matplotlib.font_manager as font_manager
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from wx.lib.wordwrap import wordwrap
import matplotlib.pyplot as plt

##############
#定义全局变量
##############
global Cur_Price,Max_Price,Min_Price,Price_Log,Counter
global initial_time,elapsed_time
global Monitor_Interval,y_Range
global Abs_folder,name_set_file

##############
#初始化数据
##############
Price_Log    = np.zeros((10000000,1))
Cur_Price    = 0
Max_Price    = 0
Counter      = 0
Min_Price    = 100000
Curce_Points = 600       # number of data points,用于绘制动态曲线

#####################################################
#从Setting.ini文件中读取Monitor_Interval,y_Range参数,
#若该文件不存在,则新建一个
#####################################################
Abs_folder    =  os.path.dirname(os.path.abspath(__file__))
name_set_file = Abs_folder +'\Setting.ini'
if os.path.exists(name_set_file):
    f = open(name_set_file,'r')    # r只读，w可写，a追加
    tem_Monitor_Gap = f.readline()  
    Monitor_Interval     = int(f.readline())
    tem_y_Range     = f.readline()
    y_Range         = int(f.readline())
    f.close()
else:
    Monitor_Interval  = 1000*30         # 监控间隔1000*10,1000*30(默认),1000*60,1000*60*5
    y_Range      = 1000            # 可选100, 500, 1000(默认)
    f = open(name_set_file,'w')    # r只读，w可写，a追加
    f.write('Monitor_Interval:' + "\n")
    f.write(str(Monitor_Interval) + "\n")
    f.write('y_Range:' + "\n")
    f.write(str(y_Range) + "\n")
    f.close()


##############
#字体
##############
font1 = {'family' : 'serif','color'  : 'darkred','weight' : 'normal',   'size'   : 8,}

##############
#其他
##############
# wxWidgets object ID for the timer

TIMER_ID = wx.NewId()
##############
#主窗体
##############
class Window(wx.Frame):
    global Monitor_Interval,y_Range
    def __init__(self, parent):
        super(Window,self).__init__(parent)  
        self.InitUI()  
        self.Centre()  
        self.Show()
        self.SetIcon(wx.Icon('bitcoin_48px.ico', wx.BITMAP_TYPE_ICO))        
        self.taskBarIcon = TaskBarIcon(self)
        # create some sizers
        mainSizer  = wx.BoxSizer(wx.VERTICAL)
        checkSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        #事件绑定
        self.Bind(wx.EVT_CLOSE, self.OnClose)  
        self.Bind(wx.EVT_ICONIZE, self.OnIconfiy) # 最小化事件绑定
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        
    def InitUI(self):
        global initial_time,elapsed_time
        global Monitor_Interval,y_Range
        global Cur_Price,Max_Price,Min_Price,Price_Log,Counter
        #静态文本条
        wx.StaticText(self,label='Top price:',          pos=(30, 310+50))
        wx.StaticText(self,label='Current price:',      pos=(30, 330+50))  
        wx.StaticText(self,label='Floor price:',        pos=(30, 350+50))
        wx.StaticText(self,label='Current time:',       pos=(210,310+50))
        wx.StaticText(self,label='Monitor interval:',   pos=(210,330+50))
        wx.StaticText(self,label='Monitor time:',       pos=(210,350+50))
        wx.StaticText(self,label='Network state:',      pos=(30, 310))
        wx.StaticText(self,label='Price trend:',        pos=(210, 310))
        #动态文本条
        self.string_top_price    = wx.StaticText(self,label='',pos=(130,310+50))
        self.string_price        = wx.StaticText(self,label='',pos=(130,330+50))
        self.string_flr_price    = wx.StaticText(self,label='',pos=(130,350+50)) 
        self.string_cur_time     = wx.StaticText(self,label='',pos=(320,310+50))
        self.string_mon_gap      = wx.StaticText(self,label='',pos=(320,330+50))
        self.string_elp_time     = wx.StaticText(self,label='',pos=(320,350+50))
        self.string_network      = wx.StaticText(self,label='',pos=(130,310))
        self.string_price_trend  = wx.StaticText(self,label='',pos=(320,310))        
        # 创建定时器  
        self.timer = wx.Timer(self)#创建定时器  
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)#绑定一个定时器事件  
        self.SetSize((500, 480))
        #窗口的颜色
        self.SetBackgroundColour('#DCDCDC')
        #窗口的标题
        self.SetTitle('Huobi Bitcoin price monitor Version 0.1')  
        self.Centre()  
        self.Show(True)
        #检查网络连接
        if Check_Network()==1:
            #查询价格,更新文本条
            self.string_price.SetLabel(str(Get_Huobi_Price()))
            self.string_top_price.SetLabel(str(Max_Price))
            self.string_flr_price.SetLabel(str(Min_Price))
            #设置网络状态指示灯为绿色
            self.string_network.SetLabel('ok')
            self.string_price_trend.SetLabel('unknow')
        else:
            self.string_price.SetLabel('0')
            self.string_top_price.SetLabel('0')
            self.string_flr_price.SetLabel('0')
            #设置网络状态指示灯为红色
            self.string_network.SetLabel('error')
            self.string_price_trend.SetLabel('unknow')
        self.string_cur_time.SetLabel(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())))
        self.string_mon_gap.SetLabel(str(int(Monitor_Interval/1000.0))+' s')
        initial_time = time.time()
        self.string_elp_time.SetLabel('0.00 mins')
        #绘制曲线相关,先生成画板
        self.fig = Figure(facecolor='#DCDCDC') #设置背景色
        self.fig.set_figheight(3)              #设置Figure高度
        self.fig.set_figwidth(5)               #设置Figure宽度    
        # bind the Figure to the backend specific canvas  
        self.canvas = FigureCanvas(self, wx.ID_ANY, self.fig)
        # add a subplot  
        self.ax = self.fig.add_subplot(111)  
        # limit the X and Y axes dimensions,以当前价格为中心,y_Range之内  
        self.ax.set_xlim([0, Curce_Points])
        if y_Range==1000:
            self.ax.set_ylim([Cur_Price-500, Cur_Price+500])
        elif y_Range==500:
            self.ax.set_ylim([Cur_Price-250, Cur_Price+250])
        elif y_Range==100:
            self.ax.set_ylim([Cur_Price-50, Cur_Price+50])
        self.ax.set_autoscale_on(False)
        if Monitor_Interval==1000*30:
            self.ax.set_xticks(np.linspace(0,600,7))  
            self.ax.set_xticklabels( ('300', '250', '200', '150', '100',  '50',  '0'),fontdict=font1)
        elif Monitor_Interval==1000*10:
            self.ax.set_xticks(np.linspace(0,600,5))  
            self.ax.set_xticklabels( ('100', '75', '50', '25', '0'),fontdict=font1)
        elif Monitor_Interval==1000*60:
            self.ax.set_xticks(np.linspace(0,600,7))  
            self.ax.set_xticklabels( ('600', '500', '400', '300', '200','100','0'),fontdict=font1)
        elif Monitor_Interval==1000*60*5:
            self.ax.set_xticks(np.linspace(0,600,7))  
            self.ax.set_xticklabels( ('3000', '2500', '2000', '1500', '1000','500','0'),fontdict=font1)
        if y_Range==1000:
            self.ax.set_yticks(range(Cur_Price-500-1, Cur_Price+500+1, 100))
            tem_array = tuple(range(Cur_Price-500-1, Cur_Price+500+1, 100))
        elif y_Range==500:
            self.ax.set_yticks(range(Cur_Price-250-1, Cur_Price+250+1, 50))
            tem_array = tuple(range(Cur_Price-250-1, Cur_Price+250+1, 50))
        elif y_Range==100:
            self.ax.set_yticks(range(Cur_Price-50-1, Cur_Price+50+1, 10))
            tem_array = tuple(range(Cur_Price-50-1, Cur_Price+50+1, 10))            
        self.ax.set_yticklabels(tem_array,fontdict=font1)
        #曲线图边框的颜色,本程序选择橘黄色
        self.ax.spines['left'].set_color('#FF9000')     
        self.ax.spines['right'].set_color('#FF9000')
        self.ax.spines['top'].set_color('#FF9000')
        self.ax.spines['bottom'].set_color('#FF9000')
        #坐标轴刻度朝向,颜色,长度,以及宽度
        self.ax.tick_params(axis='x', direction='in',colors='black',length=4, width=1)
        self.ax.tick_params(axis='y', direction='in',colors='black',length=5, width=1)
        #网格线
        self.ax.grid(True)  
        # generates first "empty" plots
        self.user = [None] * Curce_Points  
        self.l_user,=self.ax.plot(range(Curce_Points))
        #图例(此处已关闭)
        ###self.l_user,=self.ax.plot(range(Curce_Points),self.user,label='Price curve of Bitcoin')
        ##self.ax.legend(loc='upper center',ncol=4,prop=font_manager.FontProperties(size=9))
        
        # force a draw on the canvas() trick to show the grid and the legend  
        self.canvas.draw()  
        # save the clean background - everything but the line is drawn and saved in the pixel buffer background  
        self.bg = self.canvas.copy_from_bbox(self.ax.bbox)  
        # bind events coming from timer with id = TIMER_ID to the onTimer callback function  
        wx.EVT_TIMER(self, TIMER_ID, self.OnTimer)
        
        
    def __del__( self ):  
        pass  
    def OnTimer(self, evt):#显示时间事件处理函数
        global Cur_Price,Max_Price,Min_Price,Price_Log,Counter
        global initial_time,elapsed_time
        global Network_State
        #检查网络状态,只有网络连通了,才调用价格查询子程序
        if Check_Network()==1:
            Cur_Price = Get_Huobi_Price()
            #网络状态指示灯绿色
            self.string_network.SetLabel('ok')
        else:
            print ('no network')
            #网络状态指示灯红色
            self.string_network.SetLabel('error')
        self.string_price.SetLabel(str(Cur_Price))
        self.string_top_price.SetLabel(str(Max_Price))
        self.string_flr_price.SetLabel(str(Min_Price))
        self.string_cur_time.SetLabel(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())))
        self.string_mon_gap.SetLabel(str(int(Monitor_Interval/1000.0))+' s')
        elapsed_time =  time.time()-initial_time
        self.string_elp_time.SetLabel(str(round(elapsed_time/60,2))+' mins') # 转换成分钟,保留2位有效数字
        #价格趋势rise或者fall或者unchanged
        if Cur_Price > Price_Log[Counter-1]:
            self.string_price_trend.SetLabel('rise')
        elif Cur_Price == Price_Log[Counter-1]:
            self.string_price_trend.SetLabel('unchanged')
        else:
            self.string_price_trend.SetLabel('fall')
        #绘制曲线
        self.canvas.restore_region(self.bg)  
        #更新曲线数据
        temp = Cur_Price
        self.user = self.user[1:] + [temp]
        # update the plot  
        self.l_user.set_ydata(self.user)  
        # just draw the "animated" objects  
        self.ax.draw_artist(self.l_user)# It is used to efficiently update Axes data (axis ticks, labels, etc are not updated)  
        self.canvas.blit(self.ax.bbox)
        
    def OnPaint(self, event=None):
        dc = wx.PaintDC(self)
        dc.Clear() 
        pen = wx.Pen('#808A87', 1, wx.SOLID)  #1表示线宽
        dc.SetPen(pen)
        dc.DrawLine(0, 300, 500, 300)
        dc.SetPen(pen)
        dc.DrawLine(0, 340, 500, 340)
        
    def OnHide(self, event):  
        self.Hide()  
    def OnIconfiy(self, event):  
        event.Skip()
        self.Hide()  
    def OnClose(self, event):  
        self.taskBarIcon.Destroy()  
        self.Destroy()
##############
#窗体-Setting
##############
class Window_Setting(wx.Frame):
    global Monitor_Interval,y_Range
    def __init__(self):
        wx.Frame.__init__(self, None, title="Setting")
        self.InitUI()  
        self.Centre()  
        self.Show()
        self.SetIcon(wx.Icon('bitcoin_48px.ico', wx.BITMAP_TYPE_ICO))        
        # create some sizers
        mainSizer  = wx.BoxSizer(wx.VERTICAL)
        checkSizer = wx.BoxSizer(wx.HORIZONTAL)
        #两个按钮
        button_Cancel = wx.Button(self,-1, "Cancel")
        button_Cancel.SetPosition((25, 135))
        button_OK     = wx.Button(self,-1, "OK")
        button_OK.SetPosition((150, 135))
        #事件绑定
        self.Bind(wx.EVT_BUTTON, self.OnClose, button_Cancel)
        self.Bind(wx.EVT_BUTTON, self.OnButton_OK, button_OK)  
        self.Bind(wx.EVT_CLOSE, self.OnClose)  
        
    def InitUI(self):
        global initial_time,elapsed_time
        global Monitor_Interval,y_Range
        #静态文本条
        wx.StaticText(self,label='Monitor interval:',     pos=(30,30))
        wx.StaticText(self,label='Price range:',     pos=(30,80))
        #选择框
        sampleList_MonitorGap = ['10 s', '30 s', '60 s', '5 mins']
        sampleList_PriceRange = ['100 yuan', '500 yuan', '1000 yuan']
        self.ch_MonitorGap = wx.Choice(self, -1, (150, 30), choices = sampleList_MonitorGap)
        self.ch_PriceRange  = wx.Choice(self, -1, (150, 80), choices = sampleList_PriceRange)
        self.Bind(wx.EVT_CHOICE, self.EvtChoice_MonitorGap, self.ch_MonitorGap)
        self.Bind(wx.EVT_CHOICE, self.EvtChoice_PriceRange, self.ch_PriceRange)
        #窗口的颜色
        self.SetBackgroundColour('#DCDCDC')
        #窗口的标题
        self.SetTitle('Setting')
        self.SetSize((280, 230))
        self.Centre()  
        self.Show(True)
    def __del__( self ):  
        pass  
    def OnHide(self, event):  
        self.Hide()  
    def EvtChoice_MonitorGap(self, event):
        global Monitor_Interval,y_Range
        if event.GetString() == '10 s':
            Monitor_Interval = 1000*10
        elif event.GetString() == '30 s':
            Monitor_Interval = 1000*30
        elif event.GetString() == '60 s':
            Monitor_Interval = 1000*60
        elif event.GetString() == '5 mins':
            Monitor_Interval = 1000*60*5
    def EvtChoice_PriceRange(self, event):
        global Monitor_Interval,y_Range
        if event.GetString() == '100 yuan':
            y_Range = 100
        elif event.GetString() == '500 yuan':
            y_Range = 500
        elif event.GetString() == '1000 yuan':
            y_Range = 1000
    def OnClose(self, event):   
        self.Destroy()
    def OnButton_OK(self, event):
        global Monitor_Interval,y_Range,name_set_file
        #更新Setting.ini文件
        f = open(name_set_file,'w')    # r只读，w可写，a追加
        f.write('Monitor_Interval:' + "\n")
        f.write(str(Monitor_Interval) + "\n")
        f.write('y_Range:' + "\n")
        f.write(str(y_Range) + "\n")
        f.close()
        self.Destroy()
        wx.MessageBox('Settings will take effect after restaring the program!', 'Information')
##############
#任务栏图标
##############
class TaskBarIcon(wx.TaskBarIcon):
    ID_Setting = wx.NewId()
    ID_About = wx.NewId()  
    def __init__(self, frame):
        global Cur_Price,Max_Price,Min_Price,Price_Log,Counter
        wx.TaskBarIcon.__init__(self)  
        self.frame = frame
        Icon_text = 'Current price of Bitcoin is ' + str(Cur_Price)
        self.SetIcon(wx.Icon('bitcoin_48px.ico', wx.BITMAP_TYPE_ICO),Icon_text)  
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.OnTaskBarLeftDClick)
        self.Bind(wx.EVT_MENU, self.OnSetting, id=self.ID_Setting)  
        self.Bind(wx.EVT_MENU, self.OnAbout, id=self.ID_About)  
  
    def OnTaskBarLeftDClick(self, event):  
        if self.frame.IsIconized():  
           self.frame.Iconize(False)
        if not self.frame.IsShown():  
           self.frame.Show(True)
           
    def OnSetting(self, event):
        SettingWindow = Window_Setting()
        Window_Setting.Show
        
    def OnAbout(self, event):  
        ####wx.MessageBox('A python program written by Shi Fang!', 'About')
        info = wx.AboutDialogInfo()
        info.Name = "Bitcion price monitor"
        info.Version = "0.1"
        info.Copyright = "(C) 2017 PhiPsi.top"
        info.Description = "This program is used to monitor the price of Bitcoin!"
        info.WebSite = ("http://phipsi.top/author.html", "About the author")
        info.License =  "This program is an opensource program."
        info.Developers = [ "Fang Shi"]
        wx.AboutBox(info)
  
    # override  
    def CreatePopupMenu(self):  
        menu = wx.Menu()
        menu.Append(self.ID_Setting, 'Setting') 
        menu.Append(self.ID_About, 'About')  
        return menu
    
###################        
#检查网络是否正常
###################
def Check_Network():
    global Network_State
    try:
        urllib2.urlopen('http://www.baidu.com', timeout=1)
        Network_State =1
    except urllib2.URLError as err: 
        Network_State =0
    return Network_State
##############        
#获取价格
##############
def Get_Huobi_Price():
    global Cur_Price,Max_Price,Min_Price,Price_Log,Counter
    #打开网址
    Huobi_Html = urllib2.urlopen('http://api.huobi.com/staticmarket/ticker_btc_json.j')
    #读取json数据
    Huobi_json = json.loads(Huobi_Html.read())
    #提取数据,字典格式
    Data_dic = Huobi_json[u'ticker']

    #转成字符串格式
    Data_str  = str(Data_dic)
    #处理字符串,读取Last price
    Target_String   = "last"
    nPos_last_price = Data_str.index(Target_String)
    c_Price_String  = Data_str[nPos_last_price + 6:nPos_last_price +6 +5]
    #更新最大值和最小值
    Cur_Price = int(c_Price_String)
    if Cur_Price > Max_Price:
        Max_Price = Cur_Price
    if Cur_Price < Min_Price:
        Min_Price = Cur_Price
    #计数器加1
    Counter = Counter +1
    Price_Log[Counter] = Cur_Price
    #函数结束并返回值
    return Cur_Price

if __name__ == '__main__':  
    app = wx.App()  
    frame = Window(None)
    t = wx.Timer(frame, TIMER_ID)  
    t.Start(Monitor_Interval) #设定时间间隔为Monitor_Interval 
    app.MainLoop()  



