#!/usr/bin/python
# -*- coding: UTF-8 -*-
from __future__ import print_function
import os
import sys
import serial
# import threading
# import logging
# import signal
# import time
# import argparse
# import atexit
# import re
# import struct
# import ctypes
# import zlib
import time
# from enum import Enum
from copy import deepcopy
from ctypes import *
# from threading import Timer, Thread, Event
from datetime import datetime
from colorama import Fore, Back, init
import config as glb

VERSION = "0.33"
platform_types = {1: 'MAX32660'}


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


stop = False


class MaximBootloader(object):
    def __init__(self, msbl_file, port):
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = 115200
        self.ser.timeout = 300
        try:
            self.ser.open()  # open the serial port

            if self.ser.isOpen():
                print(self.ser.name + ' is open...')
        except serial.SerialException as e:
            print(e)
            print(Fore.RED + 'Cannot open serial port ' + port)
            exit(-1)

        print('\n\nInitializing bl downloader')
        self.msbl = Object()
        self.msbl.file_name = msbl_file
        self.quit_flag = False
        # print('msbl file name: ' + os.path.basename(self.msbl.file_name))

    def key_press_to_continue(self):
        try:
            input("Press enter to continue")
        except SyntaxError:
            pass
        except KeyboardInterrupt:
            print('Interrupted by Ctrl + C...')
            self.quit()

    def read_msbl_file(self):
        total_size = 0
        print('msbl file name: ' + os.path.basename(self.msbl.file_name))
        with open(self.msbl.file_name, 'rb') as f:
            # print('open file ok')
            header = MsblHeader()
            if f.readinto(header) == sizeof(header):
                # print('readinto file ok')
                print('magic: ' + str(header.magic, 'utf-8'))
                print('formatVersion: ' + str(header.formatVersion))
                print('target: ' + str(header.target, 'utf-8'))
                print('enc_type: ' + str(header.enc_type, 'utf-8'))
                print('numPages: ' + str(header.numPages))
                print('pageSize: ' + str(header.pageSize))
                print('crcSize: ' + str(header.crcSize))
                print('size of header: ' + str(sizeof(header)))

                print('resv0: ', header.resv0)
                self.print_as_hex('nonce', header.nonce)
                self.print_as_hex('auth', header.auth)
                self.print_as_hex('resv1', header.resv1)
            else:
                print('open file filed')
                return False

            self.msbl.header = header

            i = 0
            self.msbl.page = {}
            tmp_page = Page()
            last_pos = f.tell()
            total_size = total_size + sizeof(header)
            print('last_pos: ' + str(last_pos))
            while f.readinto(tmp_page) == sizeof(tmp_page):
                self.msbl.page[i] = deepcopy(tmp_page.data)
                total_size = total_size + sizeof(tmp_page)
                # print('read page ' + str(i));
                i = i + 1
                last_pos = f.tell()
            # print('last_pos: ' + str(last_pos))

            self.msbl.crc32 = CRC32()
            f.seek(-4, 2)

            f.readinto(self.msbl.crc32)
            boot_mem_page = i - 1
            total_size = total_size + sizeof(self.msbl.crc32)
            print('Total file size: ' + str(total_size) + ' CRC32: ' + hex(self.msbl.crc32.val))
            print('Reading msbl file succeed.')
        f.close()
        return True

    def set_iv(self):
        print(Fore.GREEN + '\nSet IV')
        nonce_hex = "".join("{:02X}".format(c) for c in self.msbl.header.nonce)
        print('set_iv ' + nonce_hex + '\n')
        ret = self.send_str_cmd('set_iv ' + nonce_hex + '\n')
        if ret[0] == 0:
            print('Set IV bytes succeed.')
        return ret[0]

    def set_auth(self):
        print(Fore.GREEN + '\nSet Auth')
        auth_hex = "".join("{:02X}".format(c) for c in self.msbl.header.auth)
        print('set_auth ' + auth_hex + '\n')
        ret = self.send_str_cmd('set_auth ' + auth_hex + '\n')
        if ret[0] == 0:
            print('Set Auth bytes succeed.')
        return ret[0]

    def set_num_pages(self, num_pages):
        print(Fore.GREEN + '\nSet number of pages to download')
        ret = self.send_str_cmd('num_pages ' + str(num_pages) + '\n')
        if ret[0] == 0:
            print('Set page size(' + str(num_pages) + ') successfully.')
        return ret[0]

    def erase_app(self):
        print(Fore.GREEN + '\nErase App')
        ret = self.send_str_cmd('erase\n')
        if ret[0] == 0:
            print('Erasing App flash succeed.')
        time.sleep(0.6)
        return ret[0]

    def enter_flash_mode(self):
        print(Fore.GREEN + '\nEnter flashing mode')
        ret = self.send_str_cmd('flash\n')
        if ret[0] == 0:
            print('flash command succeed.')
        else:
            print("FAILED: ret: " + str(ret))
            return ret[0]
        return ret[0]

    def enable_image_on_RAM(self, enable):
        print(Fore.GREEN + '\nEnable image on RAM: ', str(enable))
        ret = self.send_str_cmd('image_on_ram ' + str(int(enable == True)) + '\n')
        print('CMD :' + 'image_on_ram ' + str(int(enable == True)) + '\n')
        if ret[0] == 0:
            print('In image_on_ram Mode.')
        else:
            print("FAILED: ret: " + str(ret))
            return ret[0]
        return ret[0]

    def flash_image_on_RAM(self, num_pages):
        print(Fore.GREEN + '\n' + str(datetime.time(datetime.now())) + ' - Flashing Firmware on RAM')
        ret = self.send_str_cmd('image_flash\n')

        for i in range(0, num_pages):
            print("Flashing " + str(i) + "/" + str(num_pages) + " page...", end="")
            resp = self.ser.readline()
            ret = self.parse_response(resp)
            if ret[0] == 0:
                print("[DONE]")
            else:
                print("[FAILED]... ret: ", ret)

        if ret[0] == 0:
            print('flash command succeed.')
        else:
            print("FAILED: ret: " + str(ret))
            return ret[0]
        return ret[0]

    def download_page(self, page_num):
        page_bin = self.msbl.page[page_num]
        i = 0
        step = 1
        while i < (8192 + 16):
            page_part = page_bin[i: i + step]
            # print (page_part)
            self.ser.write(serial.to_bytes(page_part))
            # self.ser.write(page_part)
            i = i + step

        ret = self.parse_response("NA")
        return ret[0]

    def get_flash_page_size(self):
        print(Fore.GREEN + '\nGet page size')
        ret = self.send_str_cmd('page_size\n')
        if ret[0] == 0:
            self.page_size = int(ret[1][b'value'])
            print('Target page size: ' + str(self.page_size))
            if self.page_size != 8192:
                print('WARNING: Page size is not 8192. page_size: ' + str(self.page_size))
        else:
            print('Get page size err\n')
        return ret[0]

    def set_host_mcu(self, ebl_mode, delay_factor):
        if self.disable_echo() != 0:
            print('Unable to disable echo mode. Communication failed...')
            return False

        if not EBL_MODE.USE_TIMEOUT <= ebl_mode <= EBL_MODE.USE_GPIO:
            print("Invalid parameter")
            return False

        if self.set_host_operating_mode(ebl_mode) != 0:
            print('Unable to set mode of host to app or bootloader')
            return False

        if self.set_host_ebl_mode(ebl_mode) != 0:
            print('Unable to set EBL mode in host')
            return False

        if self.set_host_delay_factor(delay_factor) != 0:
            print('Unable to set EBL mode in host')
            return False

        return True

    ######### Bootloader #########
    def bootloader_single_download(self, reset):
        print('\nDownloading msbl file')

        if self.enter_bootloader_mode() != 0:
            print('Entering bootloader mode failed')
            return

        # if self.enable_image_on_RAM(False) != 0:
        #     print('Unable to disable image_on_RAM...')
        #     return

        # if self.get_device_info() != 0:
        #     print('Reading device info failed')

        if self.get_flash_page_size() != 0:
            print('Reading flash page size failed')
            return

        time.sleep(0.2)
        num_pages = self.msbl.header.numPages
        if self.set_num_pages(num_pages) != 0:
            print('Setting page size (', num_pages, ') failed. ')
            return

        if self.set_iv() != 0:
            print('Setting IV bytes failed.')
            return

        if self.set_auth() != 0:
            print('Setting Auth bytes failed.')
            return

        if self.erase_app() != 0:
            print('Erasing app memory failed')
            return

        if self.enter_flash_mode() != 0:
            print('Entering flash mode failed')
            return

        for i in range(0, num_pages):
            print("Flashing " + str(i + 1) + "/" + str(num_pages) + " page...", end="")
            ret = self.download_page(i)
            if ret == 0:
                print("[DONE]")
            else:
                print("[FAILED]... err: " + str(ret))
                return

        print('Flashing MSBL file succeed...')
        if reset:
            print("Resetting target...")
            if self.restart_device() != 0:
                return
        else:
            self.exit_from_bootloader()

        print(Fore.GREEN + 'SUCCEED...')
        self.close()
        # sys.exit(0)
        # self.quit()

    def bootloader_continuous_download(self, reset):
        print('\nDownloading msbl file')

        if self.enable_image_on_RAM(True) != 0:
            print('Unable to enable enable_image_on_RAM...')
            return

        time.sleep(0.2)
        num_pages = self.msbl.header.numPages
        if self.set_num_pages(num_pages) != 0:
            print('Setting page size (' + str(num_pages) + ') failed. ')
            return

        if self.set_iv() != 0:
            print('Setting IV bytes failed.')
            return

        if self.set_auth() != 0:
            print('Setting Auth bytes failed.')
            return

        if self.enter_flash_mode() != 0:
            print('Entering flash mode failed')
            return

        start = time.time()
        for i in range(0, num_pages):
            print('Downloading ' + str(i) + '/' + str(num_pages - 1) + ' page to Host RAM...')
            if self.download_page(i) != 0:
                print('Flashing ' + str(i) + '. page failed')
                return
        end = time.time()
        print("Downloading an image to host RAM takes " + str(end - start) + " sec...")

        while True:
            print(Fore.MAGENTA + '\n\n' + str(datetime.time(datetime.now()))
                  + ' - Application binary is in Host\'s RAM. Ready to Flash..')
            self.key_press_to_continue()
            if self.quit_flag:
                print("Exiting from firmware downloader")
                return

            start = time.time()
            if self.flash_image_on_RAM(num_pages - 1):
                print('Unable to flash image on RAM to target')
                return

            end = time.time()
            print("Transferring an image to target takes " + str(end - start) + " sec...")
            print(Back.BLACK + Fore.GREEN + str(datetime.time(datetime.now())) + ' Flashing SUCCEED...')
            if reset:
                if self.restart_device() != 0:
                    return
            else:
                self.exit_from_bootloader()

        print('SUCCEED...')
        self.close()
        # sys.exit(0)

    def bootloader(self, mode, reset):
        if mode == BL_MODE.SINGLE_DOWNLOAD:
            self.bootloader_single_download(reset)
        elif mode == BL_MODE.CONTINUES_DOWNLOAD:
            self.bootloader_continuous_download(reset)

    def set_host_ebl_mode(self, ebl_mode):
        print(Fore.GREEN + '\nSet timeout mode to enter bootloader')
        print('Command: set_cfg host ebl ' + str(ebl_mode) + '...' + '\n')
        ret = self.send_str_cmd('set_cfg host ebl ' + str(ebl_mode) + '\n')

        if ret[0] == 0:
            print('Set ebl_mode to ' + str(ebl_mode))
        time.sleep(0.6)
        return ret[0]

    def set_host_delay_factor(self, delay_factor):
        print(Fore.GREEN + '\nSet delay factor in host')
        print('Command: set_cfg host cdf ' + str(delay_factor) + '\n')
        ret = self.send_str_cmd('set_cfg host cdf ' + str(delay_factor) + '\n')

        if ret[0] == 0:
            print('Set bl comm delay factor to ' + str(delay_factor))
        time.sleep(0.6)
        return ret[0]

    def set_host_operating_mode(self, ebl_mode):
        print(Fore.GREEN + '\nsets mode of host to app or bootloader')
        print('Command: set_host_opmode ' + str(ebl_mode) + '\n')
        ret = self.send_str_cmd('set_host_opmode ' + str(ebl_mode) + '\n')

        if ret[0] == 0:
            print('Set host to app or bootloader ' + str(ebl_mode))
        time.sleep(0.6)
        return ret[0]

    def disable_echo(self):
        while True:
            print(Fore.GREEN + 'Command: set_host_echomode 1 ')
            ret = self.send_str_cmd('set_host_echomode 1\n')
            # print('silent_mode 1\n ')
            if ret[0] == 0:
                print('In silent mode. ret: ' + str(ret[0]))
                break
            elif ret[0] == -1:
                break
            else:
                print("Failed... ret: " + str(ret[0]) + " RETRY...")
        return ret[0]

    def parse_response(self, cmd):
        retry = 0
        while True:
            try:
                out = self.ser.readline()
            # print(out)
            except Exception as e:
                print(e)
                return [-1, {}]

            length = len(out)
            if length < 2:
                print('TRY AGAIN... send_str_cmd failed. cmd: ' + cmd + ' len: ' + str(length))
                continue

            arr = out.split(b' ')
            values = {}
            num_keys = len(arr)
            for i in range(1, num_keys):
                key_pair = arr[i].split(b'=')
                if len(key_pair) == 2:
                    values[key_pair[0]] = key_pair[1]
                else:
                    values[key_pair[0]] = b''

            retry = retry + 1
            if b'err' in values:
                break
            else:
                continue

        return [int(values[b'err']), values]

    def send_str_cmd(self, cmd):
        # length = 0
        self.ser.write(cmd.encode())
        return self.parse_response(cmd.encode())

    def get_device_info(self):
        ret = self.send_str_cmd('get_device_info\n')
        if ret[0] == 0:
            for key, value in ret[1].items():
                print(key, value)
        else:
            print('Device Info err: ' + str(ret[0]))
        return ret[0]

    def enter_bootloader_mode(self):
        ret = self.send_str_cmd('bootldr\n')
        if ret[0] != 0:
            print('Unable to enter bootloader mode... err: ' + str(ret[0]))
        else:
            print('bootldr: ' + str(ret[0]))
        return ret[0]

    def restart_device(self):
        print(Fore.GREEN + '\nRestart device')
        ret = self.send_str_cmd('reset\n')
        if ret[0] == 0:
            print('Restarting device. ret: ' + str(ret[0]))
        return ret[0]

    def exit_from_bootloader(self):
        print(Fore.GREEN + '\nJump to main application')
        ret = self.send_str_cmd('exit\n')
        if ret[0] == 0:
            print('Jumping to main application. ret: ' + str(ret[0]))
        return ret[0]

    def print_as_hex(self, label, arr):
        print(label + ' : ' + ' '.join(format(i, '02x') for i in arr))

    def quit(self):
        self.quit_flag = True
        self.close()

    def close(self):
        print("Closing")
        self.ser.close()


def fls_32664(port, msblfile):
    # print(sys.argv)
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--msblfile", required=True, type=str,
    #                     help="msbl file as input")
    # parser.add_argument("--port", required=True, type=str,
    #                     help="Serial port name in Windows")
    # args = parser.parse_args()
    init(autoreset=True)
    print(Fore.CYAN + '\n\nMAXIM FIRMWARE DOWNLOADER ' + VERSION + '\n\n')
    # ebl_mode = int(args.ebl_mode == True)
    print(">>> Parameters <<<")
    print("Mass Flash: ", False)
    print("Reset Target: ", True)
    print("EBL mode: ", 1)
    print("Delay Factor: ", 2)
    print("Port: ", port)
    print("MSBL file: ", msblfile)
    # glb.set_value('stop', False)
    # bl = MaximBootloader(msblfile, port)
    print('### Press double Ctrl + C to stop\t')
    if glb.get_value('BL') is None:
        glb.set_value('BL', MaximBootloader(msblfile, port))
        bl = glb.get_value('BL')
        try:
            if not bl.read_msbl_file():
                print('reading msbl file failed')
                raise Exception('Unable to read MSBL file')

            if not bl.set_host_mcu(1, 2):
                raise Exception('Unable to set host')

            # if args.massflash:
            #     bl.bootloader(BL_MODE.CONTINUES_DOWNLOAD, args.reset)
            # else:
            bl.bootloader(BL_MODE.SINGLE_DOWNLOAD, True)

        except KeyboardInterrupt:
            # print(result)
            bl.quit()
            sys.exit(0)
    else:
        bl = glb.get_value('BL')
        # try:
        #     q_32664()
        # except Exception as result:
        #     print(result)
        #     sys.exit(0)

        try:
            if not bl.read_msbl_file():
                print('reading msbl file failed')
                raise Exception('Unable to read MSBL file')

            if not bl.set_host_mcu(1, 2):
                raise Exception('Unable to set host')

            # if args.massflash:
            #     bl.bootloader(BL_MODE.CONTINUES_DOWNLOAD, args.reset)
            # else:
            bl.bootloader(BL_MODE.SINGLE_DOWNLOAD, True)

        except KeyboardInterrupt:
            # print(result)
            bl.quit()
            sys.exit(0)


# def q_32664():
#     if glb.get_value('stop'):
#         ex = Exception('quit')
#         raise ex

# if __name__ == '__main__':
#     main()
