# -*-coding: UTF-8 -*-
# python 3.3+
import socket
import queue
import random
import string
import re
import time

version = '0.1.0'

MSGINFO = 0
MSGERR = 1
MSGCHAT = 2
MSGPM = 3

class DCError(Exception):

    def __init__(self, error, close=None):
        """ error="текст ошибки"
            close=экземпляр DCClient, если нужно закрыть сокет и установить
                атрибут connected в False
        """
        self.error = error
        if close:
            close.connected = False
            close.socket.close()
    def __str__(self):
        return self.error


class DCSocketError(DCError):
    pass


class MsgQueue(queue.Queue):

    def mput(self, **item):
        """ MSGINFO, MSGERR, MSGCHAT:
                mput(type, text)
            MSGPM:
                mput(type, sender, text)
        """
        item['time'] = time.time()
        self.put(item, block=False)

    def mget(self):
        try:
            item = self.get(block=False)
        except queue.Empty:
            return False
        else:
            return item


class NickList():

    def __init__(self):
        self._nicks = set()

    def __contains__(self, nick):
        return nick in self._nicks

    def add(self, nick):
        self._nicks.add(nick)

    def remove(self, nick):
        try:
            self._nicks.remove(nick)
        except KeyError:
            pass


class DCClient:

    timeout = None
    debug = False
    showjoins = False

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
        self.connected = False
        self.recv_list = []
        self.message_queue = MsgQueue()
        self.nicklist = None
        self.hubname = None
        self.hubtopic = None

    def connect(self, get_nicks=False):
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
                raise DCSocketError("connection timeout ({0} s)".format(self.timeout), close=self)
            except OSError as err:
                raise DCSocketError(err.strerror, close=self)
            data = self.recv(encoding=False)   # $Lock получаем без декодирования (bytes)
            lock_received = re.search(b'^\$Lock (.+) Pk=.+$', data)
            if not lock_received:
                self.message_queue.mput(type=MSGERR, text="$Lock is not received")
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
                data = self.receive()   # тут используем высокоуровневый метод
                if not data is None:   # None означает, что команда уже была обработана в receive()
                    if data == '$GetPass':
                        if not self.password:
                            self.message_queue.mput(type=MSGERR, text="need a password")
                            return False
                        else:
                            self.send('$MyPass ' + self.password)
                            self.message_queue.mput(type=MSGINFO, text="password has been sent")
                    elif data == '$BadPass':
                        self.message_queue.mput(type=MSGERR, text="wrong password")
                        return False
                    elif data.startswith('$Supports '):
                        pass
                    elif data.startswith('$Hello '):
                        self.nick = data[7:]   # иногда хаб может выдавать другое имя
                        self.message_queue.mput(type=MSGINFO, text="Hello, {0}".format(self.nick))
                        break
                    else:
                        tries -= 1
            else:   # если вышли не по break (т.е. не получили Hello)
                self.message_queue.mput(type=MSGERR, text="$Hello was not received")
                return False
            if get_nicks:
                getnicklist = '$GetNickList'
                self.nicklist = NickList()
            else:
                getnicklist = ''
            self.send('$Version 1,0091', getnicklist, '$MyINFO $ALL {0} {1}<slangdc V:{2},M:P,H:0/1/0,S:{3}>$ $100 ${4}${5}$'.format(self.nick, self.desc, version, self.slots, self.email, self.share))
            return True
        self.message_queue.mput(type=MSGINFO, text="connecting to {0}".format(self.address))
        try:
            self.connected = _connect(self)
        except DCSocketError as err:
            self.message_queue.mput(type=MSGERR, text="[socket] {0}".format(err))
        else:
            if not self.connected:
                self.disconnect()
            else:
                self.message_queue.mput(type=MSGINFO, text="connected")
        return self.connected

    def disconnect(self):
        self.connected = False
        self.socket.close()
        self.message_queue.mput(type=MSGINFO, text="disconnected")

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
                    raise DCSocketError("receive timeout ({} s)".format(self.timeout), close=self)
                except OSError as err:
                    raise DCSocketError(err.strerror, close=self)
                if not chunk:   # len(recv) == 0 --> удаленный сокет закрыт
                    raise DCSocketError("closed", close=self)
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
            raise DCSocketError(err.strerror, close=self)

    def chat_send(self, message, encoding=None):
        self.send('<{0}> {1}'.format(self.nick, message), encoding=encoding)

    def pm_send(self, to, message, encoding=None):
        self.send('$To: {0} From: {1} $<{1}> {2}'.format(to, self.nick, message), encoding=encoding)

    def receive(self, raise_exc=True, encoding=None):
        """ высокоуровневая обёртка над recv()

            обрабатывает сообщения чата, PM, различные
            команды типа $HubName, выполняя соответствующие
            действия (кладёт в очереди, обновляет атрибуты)
            (в этом случае возвращает None)
            неизвестные команды возвращает как есть
            (т.е. ведёт себя аналогично более низкоуровневу
            recv c опциональной возможностью подавить
            исключение (см. ниже)

            перехватывает DCSocketError, после чего:
            raise_exc=True - заново возбуждает DCSocketError,
            чтобы передать его выше (по умолчанию)
            raise_exc=False - не возбуждает исключение,
            возвращает False (иными словами, подавляет
            исключение)
        """
        try:
            data = self.recv(encoding=encoding)
        except DCSocketError as err:
            self.message_queue.mput(type=MSGERR, text="[socket] {0}".format(err))
            if raise_exc:
                raise DCSocketError(str(err))
            else:
                return False
        else:
            if data:
                if not data.startswith('$'):
                    self.message_queue.mput(type=MSGCHAT, text=data)
                    return None
                elif data.startswith('$HubName '):
                    self.hubname = data[9:]
                    self.message_queue.mput(type=MSGINFO, text="HubName: {0}".format(self.hubname))
                elif data.startswith('$HubTopic '):
                    self.hubtopic = data[10:]
                    self.message_queue.mput(type=MSGINFO, text="HubTopic: {0}".format(self.hubtopic))
                    return None
                elif data.startswith('$NickList '):
                    nicklist = data[10:].split('$$')
                    for nick in nicklist:
                        if nick:
                            self.nicklist.add(nick)
                elif data.startswith('$Quit '):
                    nick = data[6:]
                    self.nicklist.remove(nick)
                    if self.showjoins:
                        self.message_queue.mput(type=MSGINFO, text="quit {0}".format(nick))
                    return None
                else:
                    pm = re.search('^\$To: .+ From: (.+) \$(.+)$', data, flags=re.DOTALL)
                    if pm:
                        self.message_queue.mput(type=MSGPM, sender=pm.group(1), text=pm.group(2))
                        return True
                    myinfo = re.search('^\$MyINFO \$ALL (.+?) ', data)
                    if myinfo:
                        nick = myinfo.group(1)
                        if not nick in self.nicklist:
                            self.nicklist.add(nick)
                            if self.showjoins:
                                self.message_queue.mput(type=MSGINFO, text="enter {0}".format(nick))
                        return True
            return data

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
