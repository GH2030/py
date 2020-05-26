import sys
import os
# import struct
# import ctypes
from copy import deepcopy
from ctypes import *
import time
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


class MsblHeader(Structure):
    _fields_ = [('magic', 4 * c_char),
                ('formatVersion', c_uint),
                ('target', 16 * c_char),
                ('enc_type', 16 * c_char),
                ('nonce', 11 * c_ubyte),
                ('resv0', c_ubyte),
                ('auth', 16 * c_ubyte),
                ('numPages', c_ushort),
                ('pageSize', c_ushort),
                ('crcSize', c_ubyte),
                ('resv1', 3 * c_ubyte)]


class AppHeader(Structure):
    _fields_ = [('crc32', c_uint),
                ('length', c_uint),
                ('validMark', c_uint),
                ('boot_mode', c_uint)]


class Page(Structure):
    _fields_ = [('data', (8192 + 16) * c_ubyte)]


class CRC32(Structure):
    _fields_ = [('val', c_uint)]


class Object(object):
    pass


bl_exit_mode = {0: 'Jump immediately',
                1: 'Wait for programmable delay',
                2: 'remain in bootloader until receive exit command'}

bl_gpio_polarities = {0: 'active low',
                      1: 'active high'}

bl_entry_check = {0: 'always enter',
                  1: 'check EBL pin'}


class BL_MODE:
    SINGLE_DOWNLOAD = 1
    CONTINUES_DOWNLOAD = 2


class EBL_MODE:
    USE_TIMEOUT = 0
    USE_GPIO = 1


com_is_open = 0
file_is_open = 0


class MAX_Serial(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MAX_Serial, self).__init__()

        self.setWindowIcon(QIcon('./Downloads.ico'))
        self.setupUi(self)

        self.msbl = Object()
        self.Com_Dict = {}

        self.init()
        self.ser = serial.Serial()
        self.ser.timeout = 0.5

        # 实例化线程对象
        self.my_thread = SerialThread(self.msbl, self.ser)
        self.my_thread.my_signal.connect(self.set_show_text_func)  # 线程自定义信号连接的槽函数

    def init(self):
        # 串口配置
        """
        self.BAUDCB.addItem('115200')
        self.DataBitCB.addItem('8')
        self.ParityCB.addItem('N')
        self.StopBitCB.addItem('1')
        self.FloCtrlCB.addItem('None')
        """

        self.BAUDCB.addItems(['1200', '2400', '4800', '9600', '19200', '115200'])
        self.DataBitCB.addItems(['5', '6', '7', '8'])
        self.ParityCB.addItems(['N', 'E', 'O', 'M', 'S'])
        self.StopBitCB.addItems(['1', '1.5', '2'])
        # self.FloCtrlCB.addItems(['None'])
        self.FloCtrlCB.addItem('None')

        self.BAUDCB.setCurrentIndex(5)
        self.DataBitCB.setCurrentIndex(3)
        self.ParityCB.setCurrentIndex(0)
        self.StopBitCB.setCurrentIndex(0)

        # 串口检测按钮
        self.ScanPortButton.clicked.connect(self.port_check)
        # 打开串口按钮
        self.OpenPortButton.clicked.connect(self.port_open)
        '''
        # 接收数据
        # self.com.readyRead()
        # 定时器接收数据
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.data_receive)
        self.timer.start(100)
        '''
        # 串口功能
        self.CleanButton.clicked.connect(self.receive_data_clear)
        self.OpenFileButton.clicked.connect(self.read_msbl_file)
        self.SendButton.clicked.connect(self.start_SerialThread)

        # 菜单栏功能
        self.actionExit.triggered.connect(self.exit_tool)
        self.actionOpen_File.triggered.connect(self.read_msbl_file)
        self.actionSaveLog.triggered.connect(self.save_log)
        # self.actionHelp.triggered.connect(self.show_about)

        # self.LogBrowser.document().setMaximumBlockCount(100)

    # 由于自定义信号时自动传递一个字符串参数，所以在这个槽函数中要接受一个参数
    def set_show_text_func(self, s):
        self.LogBrowser.append(s)

    def start_SerialThread(self):
        global com_is_open
        global file_is_open
        if com_is_open and file_is_open:
            if self.SendButton.text() == '发送文件':
                self.SendButton.setText('停止发送')
                self.OpenPortButton.setEnabled(False)
                # 启动线程
                self.my_thread.working = True
                self.my_thread.start()
            else:
                self.SendButton.setText('发送文件')
                self.OpenPortButton.setEnabled(True)
                self.my_thread.working = False
                self.my_thread.terminate()

        else:
            if com_is_open == 0:
                QMessageBox.information(self, "Port Info", "没有打开串口")
            if file_is_open == 0:
                QMessageBox.information(self, "File Info", "没有打开文件")

    # 串口检测
    def port_check(self):
        # 检测所有存在的串口，将信息存储在字典中
        port_list = list(serial.tools.list_ports.comports())
        self.COMCB.clear()
        for port in port_list:
            self.Com_Dict["%s" % port[0]] = "%s" % port[1]
            self.COMCB.addItem(port[0])
        if len(self.Com_Dict) == 0:
            # self.COMCB.addItem("无串口")
            # QMessageBox.critical(self, "Port Info", "无串口")
            QMessageBox.information(self, "Port Info", "没有发现可用串口")

    def port_open(self):
        global com_is_open
        # time.sleep(0.1)
        if self.OpenPortButton.text() == "打开串口":
            self.ser.close()
            self.ser.port = self.COMCB.currentText()
            self.ser.baudrate = int(self.BAUDCB.currentText())
            self.ser.bytesize = int(self.DataBitCB.currentText())
            self.ser.stopbits = int(self.StopBitCB.currentText())
            self.ser.parity = self.ParityCB.currentText()

            try:
                self.ser.open()
                if self.ser.isOpen():
                    self.COMCB.setEnabled(False)
                    self.BAUDCB.setEnabled(False)
                    self.DataBitCB.setEnabled(False)
                    self.ParityCB.setEnabled(False)
                    self.StopBitCB.setEnabled(False)
                    self.FloCtrlCB.setEnabled(False)
                    self.ScanPortButton.setEnabled(False)
                    self.OpenPortButton.setText("关闭串口")
                    # self.LogBrowser.append(self.ser.name + ' is open...')
                    com_is_open = 1
                else:
                    self.LogBrowser.append(self.ser.name + ' Cannot open serial port...')
            except serial.SerialException:
                # QMessageBox.critical(self, "Critical", "无法打开串口！！")  # 打开失败，弹窗提示
                QMessageBox.information(self, "Port Info", "无法打开串口")
                # print(self.ser.name + ' Cannot open serial port...')
                return None
        else:
            self.ser.close()
            self.my_thread.terminate()
            self.OpenPortButton.setText("打开串口")
            self.COMCB.setEnabled(True)
            self.BAUDCB.setEnabled(True)
            self.DataBitCB.setEnabled(True)
            self.ParityCB.setEnabled(True)
            self.StopBitCB.setEnabled(True)
            self.FloCtrlCB.setEnabled(True)
            self.ScanPortButton.setEnabled(True)
            # self.LogBrowser.append(self.ser.name + ' is closed...')
            com_is_open = 0

    def data_receive(self):
        try:
            num = self.ser.inWaiting()
        except Exception as e:
            print(e)
            self.ser.close()
            self.OpenPortButton.setText("打开串口")
            self.COMCB.setEnabled(True)
            self.BAUDCB.setEnabled(True)
            self.DataBitCB.setEnabled(True)
            self.ParityCB.setEnabled(True)
            self.StopBitCB.setEnabled(True)
            self.FloCtrlCB.setEnabled(True)
            return None
        if num > 0:
            data = self.ser.read(num)
            self.LogBrowser.append(data.decode('GBK'))
            # print(data)

        else:
            pass

    def receive_data_clear(self):
        self.LogBrowser.clear()

    def read_msbl_file(self):
        global file_is_open
        total_size = 0
        msblfile_name = QFileDialog.getOpenFileName(self, '选择文件', './', 'msbl文件(*.msbl)')
        # print(msblfile_name)
        msblfile_name_path = msblfile_name[0]
        if msblfile_name_path != '':
            header = MsblHeader()
            # print(sizeof(header))
            # self.LogBrowser.setPlainText('Open File: ' + msblfile_name_path)
            self.FileLineEdit.setText(msblfile_name_path)
            self.LogBrowser.append('File Name: ' + os.path.basename(msblfile_name_path))
            # print("msblfile_name_path is not None")
            with open(msblfile_name_path, 'rb') as f:
                # header = f.read(sizeof(header))
                if f.readinto(header) == sizeof(header):
                    self.LogBrowser.append('magic: ' + str(header.magic, 'utf-8')
                                           + '  formatVersion: ' + str(header.formatVersion)
                                           + '  target: ' + str(header.target, 'utf-8')
                                           + '  enc_type: ' + str(header.enc_type, 'utf-8')
                                           + '  numPages: ' + str(header.numPages)
                                           + '  pageSize: ' + str(header.pageSize)
                                           + '  crcSize: ' + str(header.crcSize)
                                           + ' size of header: ' + str(sizeof(header)))
                    # print('  resv0: ', str(header.resv0))
                    self.LogBrowser.append("resv0: " + str(header.resv0))
                    self.print_as_hex('nonce', header.nonce)
                    self.print_as_hex('auth', header.auth)
                    self.print_as_hex('resv1', header.resv1)
                self.msbl.header = header
                # print(msbl.header)

                i = 0
                self.msbl.page = {}
                tmp_page = Page()
                last_pos = f.tell()
                total_size = total_size + sizeof(header)
                self.LogBrowser.append('last_pos: ' + str(last_pos))
                while f.readinto(tmp_page) == sizeof(tmp_page):
                    self.msbl.page[i] = deepcopy(tmp_page.data)
                    total_size = total_size + sizeof(tmp_page)
                    # print("read page " + str(i));
                    i = i + 1
                    last_pos = f.tell()
                    # print('last_pos: ' + str(last_pos))
                self.msbl.crc32 = CRC32()
                f.seek(-4, 2)

                f.readinto(self.msbl.crc32)
                total_size = total_size + sizeof(self.msbl.crc32)
                self.LogBrowser.append('Total file size: ' + str(total_size) + ' CRC32: ' + hex(self.msbl.crc32.val))
                self.LogBrowser.append('<font color=\"#228b22\">' + '\n Reading msbl file succeed.')
                file_is_open = 1

            f.close()
        else:
            # print("msblfile_name_path is None")
            self.LogBrowser.append('\n No File Selected')
            self.FileLineEdit.clear()
            file_is_open = 0

    def print_as_hex(self, label, arr):
        self.LogBrowser.append(label + ' : ' + ' '.join(format(i, '02x') for i in arr))

    def exit_tool(self):
        if self.ser.isOpen():
            self.ser.close()
        self.close()

    def save_log(self):
        log_text = self.LogBrowser.toPlainText()
        logfile_name = QFileDialog.getSaveFileName(self, '保存文件', './', 'text(*.txt)')
        # print(logfile_name)
        log_name_path = logfile_name[0]
        if log_name_path != '':
            with open(log_name_path, 'w') as logfile:
                logfile.write(log_text)
                logfile.close()
                self.LogBrowser.append('\n Save Log File Succeed.')
        else:
            # print('log_name_path is None')
            self.LogBrowser.append('\n Save Log File Failed.')

    def show_about(self):
        self.about_ui = Ui_Windows()
        self.about_ui.show()


class Ui_Windows(QtWidgets.QDialog, Ui_About):

    def __init__(self):
        super(Ui_Windows, self).__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon("./Downloads.ico"))


class SerialThread(QThread):  # 线程类
    my_signal = pyqtSignal(str)  # 自定义信号对象.参数str就代表这个信号可以传一个字符串

    def __init__(self, _msbl, _ser):
        super(SerialThread, self).__init__()
        self.msbl = _msbl
        self.ser = _ser
        self.working = False
        # self.num = 0

    def __del__(self):
        # 线程状态改变与线程终止
        self.working = False
        self.wait()
        # self.terminate()
        # self.exit()

    def set_iv(self):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nSet IV')
        nonce_hex = "".join("{:02X}".format(c) for c in self.msbl.header.nonce)
        self.my_signal.emit('set_iv ' + nonce_hex + '\n')
        ret = self.send_str_cmd('set_iv ' + nonce_hex + '\n')
        if ret[0] == 0:
            self.my_signal.emit('Set IV bytes succeed.')
        return ret[0]

    def set_auth(self):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nSet Auth')
        auth_hex = "".join("{:02X}".format(c) for c in self.msbl.header.auth)
        self.my_signal.emit('set_auth ' + auth_hex + '\n')
        ret = self.send_str_cmd('set_auth ' + auth_hex + '\n')
        if ret[0] == 0:
            self.my_signal.emit('Set Auth bytes succeed.')
        return ret[0]

    def set_num_pages(self, num_pages):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nSet number of pages to download')
        ret = self.send_str_cmd('num_pages ' + str(num_pages) + '\n')
        if ret[0] == 0:
            self.my_signal.emit('Set page size(' + str(num_pages) + ') successfully.')
        return ret[0]

    def erase_app(self):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nErase App')
        ret = self.send_str_cmd('erase\n')
        if ret[0] == 0:
            self.my_signal.emit('Erasing App flash succeed.')
        time.sleep(0.6)
        return ret[0]

    def enter_flash_mode(self):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nEnter flashing mode')
        ret = self.send_str_cmd('flash\n')
        if ret[0] == 0:
            self.my_signal.emit('flash command succeed.')
        else:
            self.my_signal.emit("FAILED: ret: " + str(ret))
            return ret[0]
        return ret[0]

    def download_page(self, page_num):
        page_bin = self.msbl.page[page_num]
        i = 0
        step = 1
        while i < (8192 + 16):
            page_part = page_bin[i: i + step]
            self.ser.write(serial.to_bytes(page_part))
            # self.ser.write(page_part)
            i = i + step

        ret = self.parse_response('download page\n'.encode())
        return ret[0]

    def get_flash_page_size(self):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nGet page size')
        ret = self.send_str_cmd('page_size\n')
        if ret == 0:
            page_size = int(ret[1]['value'])
            self.my_signal.emit('Target page size: ' + str(page_size))
            if page_size != 8192:
                self.my_signal.emit('WARNING: Page size is not 8192. page_size: ' + str(page_size))
        return ret[0]

    def set_host_mcu(self, ebl_mode, delay_factor):

        if self.set_host_operating_mode(ebl_mode) != 0:
            self.my_signal.emit('<font color=\"#ff4040\">' + 'Unable to set mode of host to app or bootloader')
            return False

        if self.disable_echo() != 0:
            self.my_signal.emit('<font color=\"#ff4040\">' + 'Unable to disable echo mode. Communication failed...')
            return False

        if self.set_host_ebl_mode(ebl_mode) != 0:
            self.my_signal.emit('<font color=\"#ff4040\">' + 'Unable to set EBL mode in host')
            return False

        if self.set_host_delay_factor(delay_factor) != 0:
            self.my_signal.emit('<font color=\"#ff4040\">' + 'Unable to set EBL mode in host')
            return False

        return True

    def set_host_ebl_mode(self, ebl_mode):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nSet timeout mode to enter bootloader')
        self.my_signal.emit('Command: set_cfg host ebl ' + str(ebl_mode) + '...' + '\n')
        ret = self.send_str_cmd('set_cfg host ebl ' + str(ebl_mode) + '\n')
        if ret[0] == 0:
            self.my_signal.emit('Set ebl_mode to ' + str(ebl_mode))
        time.sleep(0.6)
        return ret[0]

    def set_host_delay_factor(self, delay_factor):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nSet delay factor in host')
        self.my_signal.emit('Command: set_cfg host cdf ' + str(delay_factor) + '\n')
        ret = self.send_str_cmd('set_cfg host cdf ' + str(delay_factor) + '\n')
        if ret[0] == 0:
            self.my_signal.emit('Set bl comm delay factor to ' + str(delay_factor))
        time.sleep(0.6)
        return ret[0]

    def set_host_operating_mode(self, ebl_mode):
        # print(ebl_mode)
        self.my_signal.emit('<font color=\"#228b22\">' + '\nsets mode of host to app or bootloader')
        self.my_signal.emit('Command: set_host_opmode ' + str(ebl_mode) + '\n')
        ret = self.send_str_cmd('set_host_opmode ' + str(ebl_mode) + '\n')
        # print(ret[0])
        if ret[0] == 0:
            self.my_signal.emit('<font color=\"#228b22\">' + 'Set host to app or bootloader ' + str(ebl_mode))
        time.sleep(0.6)
        return ret[0]

    def disable_echo(self):
        while True:
            self.my_signal.emit('Command: set_host_echomode 1 ')
            ret = self.send_str_cmd('set_host_echomode 1\n')
            # print('silent_mode 1\n ')
            if ret[0] == 0:
                self.my_signal.emit('In silent mode. ret: ' + str(ret[0]))
                break
            elif ret[0] == -1:
                break
            else:
                self.my_signal.emit("Failed... ret: " + str(ret[0]) + " RETRY...")
        return ret[0]

    def parse_response(self, cmd):
        retry = 0
        while True:
            try:
                # out = self.ser.readline()
                out = self.ser.inWaiting()
                # self.ser.timeout = 0.5
                # print(out)
            except Exception as e:
                print(e)
                self.my_signal.emit('Serail Exception\n')
                return [-1, {}]
            if out > 0:
                data = self.ser.read(out)
                # print(data)
                length = len(data)
                # print(' len: ' + str(length))
                if length < 2:
                    # print('length < 2')
                    self.my_signal.emit('TRY AGAIN... send_str_cmd failed. cmd: ' + str(cmd, 'utf-8') + ' len: ' + str(length))
                    continue
                    # return [-2, {}]
                else:
                    arr = data.split(b' ')  # 分割字符串
                    values = {}
                    num_keys = len(arr)
                    # print(num_keys)
                    for i in range(1, num_keys):
                        key_pair = arr[i].split(b'=')
                        if len(key_pair) == 2:
                            values[key_pair[0]] = key_pair[1]
                        else:
                            values[key_pair[0]] = b''

                retry = retry + 1
                if b'err' in values:
                    # return [int(values[b'err']), values]
                    break
                else:
                    continue
                    # return [-3, {}]
                    # break
                    # return [int(values[b'err']), values]
            else:
                pass
        # return [-3, {}]
        return [int(values[b'err']), values]

    def send_str_cmd(self, cmd):
        # length = 0
        self.ser.write(cmd.encode())
        print(cmd)
        return self.parse_response(cmd.encode())

    def get_device_info(self):
        ret = self.send_str_cmd('get_device_info\n')
        # ret = self.send_str_cmd('get_device_info err=0\n')
        if ret[0] == 0:
            for key, value in ret[1].items():
                # print(key, value)
                self.my_signal.emit(str(key) + ':' + str(value))
        else:
            self.my_signal.emit('Device Info err: ' + str(ret[0]))
        return ret[0]

    def enter_bootloader_mode(self):
        ret = self.send_str_cmd('bootldr\n')
        # ret = self.send_str_cmd('bootldr err=0\n')
        if ret[0] != 0:
            self.my_signal.emit('Unable to enter bootloader mode... err: ' + str(ret[0]))
        return ret[0]

    def restart_device(self):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nRestart device')
        ret = self.send_str_cmd('reset\n')
        if ret[0] == 0:
            self.my_signal.emit('Restarting device. ret: ' + str(ret[0]))
        return ret[0]

    def exit_from_bootloader(self):
        self.my_signal.emit('<font color=\"#228b22\">' + '\nJump to main application')
        ret = self.send_str_cmd('exit\n')
        if ret[0] == 0:
            self.my_signal.emit('Jumping to main application. ret: ' + str(ret[0]))
        return ret[0]

    def run(self):
        while self.working:

            if not self.set_host_mcu(1, 2):
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Unable to set host')
                return

            self.my_signal.emit("\n Downloading msbl file")

            if self.enter_bootloader_mode() != 0:
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Entering bootloader mode failed')
                return

            # if self.get_device_info() != 0:
            # self.my_signal.emit('Reading device info failed')
            # return

            if self.get_flash_page_size() != 0:
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Reading flash page size failed')
                return

            time.sleep(0.2)
            num_pages = self.msbl.header.numPages
            if self.set_num_pages(num_pages) != 0:
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Setting page size (', num_pages, ') failed.')
                return

            if self.set_iv() != 0:
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Setting IV bytes failed.')
                return

            if self.set_auth() != 0:
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Setting Auth bytes failed.')
                return

            if self.erase_app() != 0:
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Erasing app memory failed')
                return

            if self.enter_flash_mode() != 0:
                self.my_signal.emit('<font color=\"#ff4040\">' + 'Entering flash mode failed')
                return

            for i in range(0, num_pages):
                self.my_signal.emit("Flashing " + str(i) + "/" + str(num_pages) + " page...")
                ret = self.download_page(i)
                if ret == 0:
                    self.my_signal.emit('<font color=\"#228b22\">' + '[DONE]')
                else:
                    self.my_signal.emit('<font color=\"#ff4040\">' + '[FAILED]... err: ' + str(ret))
                    return

            self.my_signal.emit('Flashing MSBL file succeed...')
            reset = 0
            if reset:
                self.my_signal.emit('<font color=\"#228b22\">' + 'Resetting target...')
                if self.restart_device() != 0:
                    self.my_signal.emit('<font color=\"#ff4040\">' + 'Restart device failed')
                    return
            else:
                if self.exit_from_bootloader() != 0:
                    self.my_signal.emit('<font color=\"#ff4040\">' + 'Jump to main application failed')
                    return

            self.my_signal.emit('<font color=\"#228b22\">' + 'SUCCEED...')
            self.working = False
            self.SendButton.setText('发送文件')
            self.OpenPortButton.setEnabled(True)
            # self.terminate()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    first = MAX_Serial()
    first.show()
    # first.pushButton.clicked.connect(first.loginEvent)
    first.actionHelp.triggered.connect(first.show_about)
    sys.exit(app.exec_())
