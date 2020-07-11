# -*- coding: utf-8 -*-
import sys
# import os
# import struct
# import ctypes
# from copy import deepcopy
# from ctypes import *
# import time
import serial
import serial.tools.list_ports
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMessageBox
# from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
# from PyQt5.QtCore import QFile, QDataStream, QIODevice, QPoint
# from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon
# from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog
from PyQt5.QtWidgets import QFileDialog
# from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QThread, pyqtSignal
from UI_Windows import Ui_MainWindow
from UI_About import Ui_About
import images_rc
import download_fw
import config as gl

# from download_fw import MaximBootloader
# import win32con
# from win32process import SuspendThread, ResumeThread


# com_is_open = 0
# file_is_open = 0
# COM = ''
# MSBLF = ''


class MAX_Serial(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MAX_Serial, self).__init__()

        self.setWindowIcon(QIcon(':/Downloads.ico'))
        self.setupUi(self)

        self.Com_Dict = {}

        self.init()

        gl._init()

        self.my_thread = SerialThread()
        self.my_thread.setTerminationEnabled(True)
        self.my_thread.my_signal.connect(self.flash_ok)  # 线程自定义信号连接的槽函数

    def init(self):
        print('程序启动\n'
              '使用步骤：\n'
              '1.点击‘扫描串口‘按钮;\n'
              '2.点击‘选择文件’按钮，选择msbl文件（文件路径不要有空格）;\n'
              '3.点击’下载文件‘按钮下载文件（可再次点击停止下载），等待执行结束。\n')
        # 串口配置
        """
        self.BAUDCB.addItem('115200')
        self.DataBitCB.addItem('8')
        self.ParityCB.addItem('N')
        self.StopBitCB.addItem('1')
        self.FloCtrlCB.addItem('None')
        """

        # self.FloCtrlCB.addItems(['None'])

        # 串口检测按钮
        self.ScanPortButton.clicked.connect(self.port_check)
        self.COMCB.currentTextChanged.connect(self.scom)

        '''
        # 接收数据
        # self.com.readyRead()
        # 定时器接收数据
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.data_receive)
        self.timer.start(100)
        '''
        # 串口功能
        # self.CleanButton.clicked.connect(self.receive_data_clear)
        self.OpenFileButton.clicked.connect(self.read_msbl_file)
        self.SendButton.clicked.connect(self.fw)

        # 菜单栏功能
        self.actionExit.triggered.connect(self.exit_tool)
        self.actionOpen_File.triggered.connect(self.read_msbl_file)
        # self.actionSaveLog.triggered.connect(self.save_log)
        # self.actionHelp.triggered.connect(self.show_about)

        # self.LogBrowser.document().setMaximumBlockCount(100)
    def scom(self):
        if self.COMCB.currentText():
            print('当前串口：' + self.COMCB.currentText())
        else:
            pass

    def flash_ok(self, s):
        print(s)
        self.SendButton.setText('下载文件')
        self.COMCB.setEnabled(True)
        self.ScanPortButton.setEnabled(True)
        self.OpenFileButton.setEnabled(True)
        self.my_thread.working = False
        self.my_thread.terminate()

    # 串口检测
    def port_check(self):
        print('扫描串口')
        # global com_is_open
        # global COM
        # 检测所有存在的串口，将信息存储在字典中
        port_list = list(serial.tools.list_ports.comports())
        self.COMCB.clear()
        for port in port_list:
            self.Com_Dict["%s" % port[0]] = "%s" % port[1]
            self.COMCB.addItem(port[0])
            # COM = self.COMCB.currentText()
            # config.set_var(COM, self.COMCB.currentText())
            gl.set_value('COM', self.COMCB.currentText())
            # print('-p ' + COM)
            # com_is_open = 1
            # config.set_var(com_is_open, 1)
            gl.set_value('com_is_open', 1)
        if len(self.Com_Dict) == 0:
            # self.COMCB.addItem("无串口")
            # QMessageBox.critical(self, "Port Info", "无串口")
            QMessageBox.information(self, "Port Info", "没有发现可用串口")
            # com_is_open = 0
            # config.set_var(com_is_open, 0)
            gl.set_value('com_is_open', 0)

    def read_msbl_file(self):
        # global file_is_open
        # global MSBLF
        msblfile_name = QFileDialog.getOpenFileName(self, '选择文件', './', 'msbl文件(*.msbl)')
        # print(msblfile_name)
        msblfile_name_path = msblfile_name[0]
        # MSBLF = msblfile_name_path
        gl.set_value('MSBLF', msblfile_name_path)

        if msblfile_name_path != '':
            self.FileLineEdit.setText(msblfile_name_path)
            print('选择文件：' + msblfile_name_path)
            # file_is_open = 1
            gl.set_value('file_is_open', 1)
        else:
            # print("msblfile_name_path is None")
            # QMessageBox.information(self, "File Info", 'No File Selected')
            print('未选择文件')
            self.FileLineEdit.clear()
            # file_is_open = 0
            gl.set_value('file_is_open', 0)

    def fw(self):
        # global com_is_open
        # global file_is_open
        # global COM
        # global MSBLF
        # if com_is_open and file_is_open:
        if gl.get_value('com_is_open') == 1 and gl.get_value('file_is_open') == 1:
            if self.SendButton.text() == '下载文件':
                print('下载线程开始')
                self.SendButton.setText('停止下载')
                # self.OpenPortButton.setEnabled(False)
                self.ScanPortButton.setEnabled(False)
                self.COMCB.setEnabled(False)
                self.OpenFileButton.setEnabled(False)

                self.my_thread.working = True
                self.my_thread.start()
                # download_fw.fls_32664(self.COMCB.currentText(), self.FileLineEdit.text())
            else:
                self.SendButton.setText('下载文件')
                print('下载线程停止')
                gl.set_value('stop', True)
                # print(self.COMCB.currentText())
                # download_fw.co_32664(self.COMCB.currentText(), self.FileLineEdit.text())
                # download_fw.MaximBootloader.co_port(MSBLF, COM)
                # self.OpenPortButton.setEnabled(True)
                self.COMCB.setEnabled(True)
                self.ScanPortButton.setEnabled(True)
                self.OpenFileButton.setEnabled(True)
                self.my_thread.working = False
                self.my_thread.terminate()
        else:
            if gl.get_value('com_is_open') is None or gl.get_value('com_is_open') == 0:
                QMessageBox.information(self, "Port Info", "没有选择串口")
            if gl.get_value('file_is_open') is None or gl.get_value('file_is_open') == 0:
                QMessageBox.information(self, "File Info", "没有选择文件")

    def exit_tool(self):
        self.close()
        sys.exit()

    def show_about(self):
        self.about_ui = Ui_Windows()
        self.about_ui.show()


class Ui_Windows(QtWidgets.QDialog, Ui_About):

    def __init__(self):
        super(Ui_Windows, self).__init__()
        self.setWindowIcon(QIcon(':/Downloads.ico'))
        self.setupUi(self)


class SerialThread(QThread):  # 线程类
    my_signal = pyqtSignal(str)  # 自定义信号对象.参数str就代表这个信号可以传一个字符串

    # handle = -1

    def __init__(self):
        super(SerialThread, self).__init__()
        # self.msbl = _msbl
        # self.ser = _ser
        self.working = False
        # self.num = 0

    def run(self):
        while self.working:
            # print(MSBLF)
            # ret = os.system(command='python download_fw.py %s %s' % (COM, MSBLF))
            # print('ret ' + str(ret))
            # if not ret:
            #     self.my_signal.emit('')
            # os.popen('python download_fw.py %s %s' % (COM, MSBLF))
            # download_fw.fls_32664(COM, MSBLF)
            download_fw.fls_32664(gl.get_value('COM'), gl.get_value('MSBLF'))
            self.my_signal.emit('下载线程执行结束')
            self.working = False
            break


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    first = MAX_Serial()
    first.show()
    # first.pushButton.clicked.connect(first.loginEvent)
    first.actionHelp.triggered.connect(first.show_about)
    sys.exit(app.exec_())
