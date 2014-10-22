# -*-coding: UTF-8 -*-
# python 3.3+
import socket
import queue
import random
import string
import re

version = '0.1.0'

class DCError(Exception):

    def __init__(self, error, close=None):
        """ error="текст ошибки"
            close=<socket object>, который надо закрыть, или None
        """
        self.error = error
        if close:
            close.close()   # закрываем сокет
    def __str__(self):
        return self.error


class DCSocketError(DCError):
    pass


class MQueue(queue.Queue):

    def mput(self, item):
        self.put(item, block=False)

    def mget(self):
        try:
            item = self.get(block=False)
        except queue.Empty:
            return False
        else:
            return item


class DCClient:

    timeout = None
    debug = False

    def __init__(self, address, nick=None, password=None, desc="", email="", share=0, slots=1, encoding='utf-8', timeout=None):
        """ address='dchub.com[:port]'
                стандартный порт (411) можно не указывать
            nick='nick'
                если не указывать, будет рандомный вида 'sldc[A-Z]{6}'
            password='password'
                можно не указывать, если не требуется
            encoding='enc'
                кодировка хаба, по умолчанию utf-8
            timeout=sec
                таймаут получения данных из сокета в секундах; по таймауту
                recv() возбуждает DCError
                по умолчанию __class__.timeout=None -->
                http://docs.python.org/3.4/library/socket.html#socket-timeouts
        """
        self.address = address
        self.nick = nick if nick else 'sldc' + ''.join(random.choice(string.ascii_uppercase) for n in range(6))
        self.password = password
        self.desc = desc
        self.email = email
        self.share = share
        self.slots = slots
        self.encoding = encoding
        if timeout: self.timeout = timeout
        self.recv_list = []
        self.message_queue = MQueue()
        self.hubname = None
        self.hubtopic = None

    def connect(self):
        """ подключиться к хабу
            возвращает True или False
        """
        def _connect(self):
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            host, _, port = self.address.partition(':')
            try:
                port = int(port)
            except ValueError:
                port = 411
            try:
                self.socket.connect((host, port))
            except socket.timeout:
                raise DCSocketError("connection timeout ({0} s)".format(self.timeout), close=self.socket)
                return False
            except OSError as err:
                raise DCSocketError(err.strerror, close=self.socket)
                return False
            data = self.recv(encoding=False)   # $Lock получаем без декодирования (bytes)
            lock_received = re.search(b'^\$Lock (.+) Pk=.+$', data)
            if not lock_received:
                self.message_queue.mput("*** $Lock is not received")
                return False
            lock = lock_received.group(1)
            if lock.startswith(b'EXTENDEDPROTOCOL'):   # EXTENDEDPROTOCOL - поддерживаются расширения протокола
                supports = '$Supports HubTopic'
            else:
                supports = ''
            key = self.lock2key(lock)
            self.send(supports, b'$Key ' + key, '$ValidateNick ' + self.nick)
            tries = 10
            while tries:
                data = self.recv()
                if not data.startswith('$'):
                    self.message_queue.mput(data)
                elif data == '$GetPass':
                    if not self.password:
                        self.message_queue.mput("*** need a password")
                        return False
                    else:
                        self.send('$MyPass ' + self.password)
                        self.message_queue.mput("*** password has been sent")
                elif data == '$BadPass':
                    self.message_queue.mput("*** wrong password")
                    return False
                elif data.startswith('$HubName '):
                    self.hubname = data[9:]
                    self.message_queue.mput("*** HubName: {0}".format(self.hubname))
                elif data.startswith('$HubTopic '):
                    self.hubtopic = data[10:]
                    self.message_queue.mput("*** HubTopic: {0}".format(self.hubtopic))
                elif data.startswith('$Supports '):
                    pass
                elif data.startswith('$Hello '):
                    self.nick = data[7:]   # иногда хаб может выдавать другое имя
                    self.message_queue.mput("*** Hello, {0}".format(self.nick))
                    break
                else:
                    tries -= 1
            else:   # если вышли не по break (т.е. не получили Hello)
                self.message_queue.mput("*** $Hello was not received")
                return False
            self.send('$Version 1,0091', '$MyINFO $ALL {0} {1}<slangdc V:{2},M:P,H:0/1/0,S:{3}>$ $100 ${4}${5}$'.format(self.nick, self.desc, version, self.slots, self.email, self.share))
            return True

        self.message_queue.mput("*** connecting to {0}".format(self.address))
        try:
            connected = _connect(self)
        except DCSocketError as err:
            self.message_queue.mput("*** [socket] {0}".format(err))
            return False
        else:
            if not connected:
                self.disconnect()
            else:
                self.message_queue.mput("*** connected")
            return connected   # True или False

    def disconnect(self):
        self.socket.close()
        self.message_queue.mput("*** disconnected")

    def recv(self, encoding=None):
        """ recv([encoding=False|'enc'])
            возвращает одну команду DC без конечного '|':
                хаб отправил 'hello|bye|'
                recv() --> 'hello'
                recv() --> 'bye'

            возвращает str или bytearray (в зависимости от
            encoding) или False в случае ошибки или таймаута

            encoding=
                False - вернуть без декодирования (bytearray)
                'enc' - декодировать как 'enc'
                None (по умолчанию) - кодировка по умолчанию
        """
        if not self.recv_list:
            recv = bytearray()
            while True:
                try:
                    chunk = self.socket.recv(1024)
                except socket.timeout:
                    raise DCSocketError("receive timeout ({} s)".format(self.timeout), close=self.socket)
                except OSError as err:
                    raise DCSocketError(err.strerror, close=self.socket)
                if not chunk:   # len(recv) == 0 --> удаленный сокет закрыт
                    raise DCSocketError("closed", close=self.socket)
                recv.extend(chunk)
                if chunk.endswith(b'|'):
                    break
            if self.debug: print("<--", recv)
            self.recv_list = recv.rstrip(b'|').split(b'|')
        data = self.recv_list.pop(0)
        if encoding is None: encoding = self.encoding   # кодировка по умолчанию
        if not encoding:   # если encoding=False
            return data
        else:
            return data.decode(encoding=encoding, errors='replace')

    def send(self, *commands, encoding=None):
        """ send(command1, command2, …, [encoding='enc'])
            отправить в сокет b'command1|command2|…|'

            commandN может быть
                str - энкодится в указанную кодировку
                bytes|bytearray - как есть
                пустые объекты игнорируются:
                send('hello', '', b'bye') --> b'hello|bye|'

            encoding=
                'enc' - кодировать строки в 'enc'
                None (по умолчанию) - кодировка по умолчанию
        """
        data = bytearray()
        if encoding is None: encoding = self.encoding
        for command in commands:
            if command:
                if isinstance(command, str):
                    command = command.encode(encoding=encoding, errors='replace')
                data.extend(command + b'|')
        if self.debug: print("-->", data)
        try:
            self.socket.send(data)
        except OSError as err:
            raise DCSocketError(err.strerror, close=self.socket)

    def chat_send(self, message, encoding=None):
        self.send('<{0}> {1}'.format(self.nick, message), encoding=encoding)

    def pm_send(self, to, message, encoding=None):
        self.send('$To: {0} From: {1} $<{1}> {2}'.format(to, self.nick, message), encoding=encoding)

    def receive(self, encoding=None):
        try:
            data = self.recv(encoding=encoding)
        except DCSocketError as err:
            self.message_queue.mput('*** [socket] {0}'.format(err))
            return False
        else:
            if data and not data.startswith('$'):
                self.message_queue.mput(data)
            elif data.startswith('$HubTopic '):
                self.hubtopic = data[10:]
                self.message_queue.mput("*** HubTopic: {0}".format(self.hubtopic))
            else:
                pm = re.search('^\$To: .+ From: (.+) \$(.+)$', data, flags=re.DOTALL)
                if pm:
                    self.message_queue.mput("%%% PM from {0}: {1}".format(pm.group(1), pm.group(2)))
            return True

    @staticmethod
    def lock2key(lock):   # http://wiki.mydc.ru/Lock2Key
        """ вычисляет key из lock
            key - bytes или bytearray
            lock - byrearray
        """
        keylist = [lock[0] ^ lock[-1] ^ lock[-2] ^ 5]
        keylist.extend(x1 ^ x2 for x1, x2 in zip(lock, lock[1:]))
        escaping = (0, 5, 36, 96, 124, 126)
        key = bytearray()
        for x in keylist:
            x = ((x << 4) & 240) | ((x >> 4) & 15)
            if x in escaping:
                key.extend(bytes('/%DCN{:03d}%/'.format(x), 'ascii'))
            else:
                key.append(x)
        return key
