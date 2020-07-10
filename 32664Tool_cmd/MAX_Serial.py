# -*- coding: utf-8 -*-
import sys
import os
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
# import images_rc
import download_fw

# from download_fw import MaximBootloader
# import win32con
# from win32process import SuspendThread, ResumeThread


com_is_open = 0
file_is_open = 0
COM = ''
MSBLF = ''


class MAX_Serial(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MAX_Serial, self).__init__()

        self.setWindowIcon(QIcon(':/Downloads.ico'))
        self.setupUi(self)

        self.Com_Dict = {}

        self.init()

        self.my_thread = SerialThread(MSBLF, COM)

    def init(self):
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

    # 串口检测
    def port_check(self):
        global com_is_open
        global COM
        # 检测所有存在的串口，将信息存储在字典中
        port_list = list(serial.tools.list_ports.comports())
        self.COMCB.clear()
        for port in port_list:
            self.Com_Dict["%s" % port[0]] = "%s" % port[1]
            self.COMCB.addItem(port[0])
            COM = self.COMCB.currentText()
            # print('-p ' + COM)
            com_is_open = 1
        if len(self.Com_Dict) == 0:
            # self.COMCB.addItem("无串口")
            # QMessageBox.critical(self, "Port Info", "无串口")
            QMessageBox.information(self, "Port Info", "没有发现可用串口")
            com_is_open = 0

    def read_msbl_file(self):
        global file_is_open
        global MSBLF
        msblfile_name = QFileDialog.getOpenFileName(self, '选择文件', './', 'msbl文件(*.msbl)')
        # print(msblfile_name)
        msblfile_name_path = msblfile_name[0]
        MSBLF = msblfile_name_path
        # print('-f ' + msblfile_name_path)

        if msblfile_name_path != '':
            self.FileLineEdit.setText(msblfile_name_path)
            file_is_open = 1
        else:
            # print("msblfile_name_path is None")
            QMessageBox.information(self, "File Info", 'No File Selected')
            self.FileLineEdit.clear()
            file_is_open = 0

    def fw(self):
        global com_is_open
        global file_is_open
        global COM
        global MSBLF
        if com_is_open and file_is_open:
            if self.SendButton.text() == '下载文件':
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
            if com_is_open == 0:
                QMessageBox.information(self, "Port Info", "没有打开串口")
            if file_is_open == 0:
                QMessageBox.information(self, "File Info", "没有选择文件")

    def exit_tool(self):
        self.close()

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
    handle = -1

    def __init__(self, _msbl, _ser):
        super(SerialThread, self).__init__()
        self.msbl = _msbl
        self.ser = _ser
        self.working = False
        # self.num = 0

    def run(self):
        if self.working:
            print(MSBLF)
            # os.system(command='python download_fw.py %s %s' % (COM, MSBLF))
            os.popen('python download_fw.py %s %s' % (COM, MSBLF))
            # download_fw.fls_32664(COM, MSBLF)
            self.working = False


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    first = MAX_Serial()
    first.show()
    # first.pushButton.clicked.connect(first.loginEvent)
    first.actionHelp.triggered.connect(first.show_about)
    sys.exit(app.exec_())
