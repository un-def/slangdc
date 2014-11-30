slangdc
=======

A (very) simple Direct Connect library and Tk-based GUI client. Chat/private messages/userlist features only, no file sharing or any other p2p stuff.

### Requirements
* Python 3.3+
* Tk (gui.py)

### Files

* `slangdc.py` — DC library
* `example.py` — DC library usage example (sort of console client)
* `gui.py` — Tk-based GUI client
* `conf.py` — json-configs (settings, bookmarks) support module for gui.py

### GUI client

![slangdc.Tk](http://i.imgur.com/JKBLg8E.png)

##### Key bindings in message text box

* **Enter** — send message
* **Ctrl+Enter** — new line
* **Shift+Enter** — replace all '\n' with '\r' and send

##### bookmarks.json format

[{bookmark1}, {bookmark2}, …]

bookmark object keys:

* **name** — bookmark name (in Bookmarks menu) (required)
* **address** — hub address (required)
* **nick**, **desc**, **email**, **share**, **slots**, **encoding**, **timeout** — override settings.json values (optional)
