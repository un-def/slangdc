#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import slangdc

def check():
    dc = slangdc.DCClient(address='hub.dc.zet')
    dc.connect()
    incoming_pm = "$To: {0} From: {0} $<{0}> check".format(dc.nick)
    while dc.connected:
        for i in range(30):
            try:
                data = dc.recv()
            except DCSocketError as err:
                print(err)
                return False
        dc.pm_send(dc.nick, "check")
        start = time.time()
        while True:
            try:
                data = dc.recv()
            except DCSocketError as err:
                print(err)
                return False
            if data == incoming_pm:
                print("wasted:", round((time.time() - start) * 1000), "ms")
                return True
    return False

while True:
    check()
    time.sleep(10)
