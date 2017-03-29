#!/usr/bin/env python3
from enum import Enum
import getopt
import os
import re
from socket import gaierror
import sys
import telnetlib
import time
from threading import Thread, Lock


def usage():
    print("VLC remote control interface with various integrations")
    print("Usage: {0} [options]".format(sys.argv[0]))
    print("")
    print("Options:")
    print("-h            --help            Print this message and exit")
    print("-H host:port  --host=host:port  Sets the host where the VLC player is accessed. Defaults to localhost:8080")
    print("-p port       --port=port       Sets the port where the HTTP interface is exposed by this application. Defaults to 9000.")
    sys.stdout.flush()

class PlayerState(Enum):
    stop = 0
    play = 2
    pause = 3
    end = 4


class QueryValueError(ValueError):
    def __init__(self, query, value):
        self.query = query
        self.value = value


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hH:p:", ["help", "host=", "port="])
    except getopt.GetoptError as err:
        usage()
        print(err)
        sys.exit(2)
    host = "localhost:8080"
    port = 9000
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-H", "--host"):
            host = a
        elif o in ("-p", "--port"):
            port = int(a)

    try:
        h, p = host.split(':')
    except ValueError:
        h = host
        p = "8080"

    print('Attempting to connect to VLC at {0}:{1}'.format(h, p))
    sys.stdout.flush()

    try:
        t = telnetlib.Telnet(h, int(p))
    except gaierror:
        print('Connection to host failed.')
        sys.exit(1)
    except ConnectionRefusedError:
        print('Connection refused - the interface may be occupied or not available.')
        sys.exit(1)

    print('Connected!')
    sys.stdout.flush()
    status_change_line = re.compile(r'^status change: \( (.*?) \)(:.*)?\s*$')

    class Player:
        def __init__(self):
            self.state_lock = Lock()
            self._volume = 0
            self._video_title = ""
            self._playstate = PlayerState.stop
            self._curr_time = 0
            self._total_time = 0
            self._source = ""

        def set_volume(self, nv):
            self.state_lock.acquire()
            self._volume = nv
            self.state_lock.release()

        def get_volume(self):
            self.state_lock.acquire()
            value = self._volume
            self.state_lock.release()
            return value

        def set_video_title(self, nv):
            self.state_lock.acquire()
            self._video_title = nv
            self.state_lock.release()

        def get_video_title(self):
            self.state_lock.acquire()
            value = self._video_title
            self.state_lock.release()
            return value

        def set_playstate(self, nv):
            self.state_lock.acquire()
            self._playstate = nv
            self.state_lock.release()
            print('Playstate change: {0}', nv)
            sys.stdout.flush()

        def get_playstate(self):
            self.state_lock.acquire()
            value = self._playstate
            self.state_lock.release()
            return value

        def set_curr_time(self, nv):
            self.state_lock.acquire()
            self._curr_time = nv
            self.state_lock.release()

        def get_curr_time(self):
            self.state_lock.acquire()
            value = self._curr_time
            self.state_lock.release()
            return value

        def set_total_time(self, nv):
            self.state_lock.acquire()
            self._total_time = nv
            self.state_lock.release()

        def get_total_time(self):
            self.state_lock.acquire()
            value = self._total_time
            self.state_lock.release()
            return value

        def set_source(self, nv):
            self.state_lock.acquire()
            self._source = nv
            self.state_lock.release()

        def get_source(self):
            self.state_lock.acquire()
            value = self._source
            self.state_lock.release()
            return value

        def inc_curr_time_if_playing(self):
            self.state_lock.acquire()
            if self._playstate == PlayerState.play:
                self._curr_time = self._curr_time + 1
            self.state_lock.release()

        volume = property(get_volume, set_volume)
        video_title = property(get_video_title, set_video_title)
        playstate = property(get_playstate, set_playstate)
        curr_time = property(get_curr_time, set_curr_time)
        total_time = property(get_total_time, set_total_time)
        source = property(get_source, set_source)

    print('Player creating.')
    sys.stdout.flush()
    player = Player()
    print('Player created.')
    sys.stdout.flush()

    def sc_volume(mc):
        nonlocal player
        player.volume = int(mc.group(1))

    def sc_playing(mc):
        nonlocal player
        player.playstate = PlayerState.play

    def sc_paused(mc):
        nonlocal player
        player.playstate = PlayerState.pause

    def sc_stopped(mc):
        nonlocal player
        player.playstate = PlayerState.end

    def sc_new_input(mc):
        nonlocal player
        src = mc.group(1)
        if re.match(r'[A-Z]:/', src):
            src = src.replace('/', '\\')
        player.source = src
        print('New input: {0}'.format(src))
        sys.stdout.flush()

    status_changes = [
        ("volume", re.compile(r'^audio volume: (-?[0-9]+)$'), sc_volume),
        ("stop", re.compile(r'^stop state: 0$'), sc_stopped),
        ("play", re.compile(r'^play state: 2$'), sc_playing),
        ("play", re.compile(r'^play state: 3$'), sc_playing),
        ("play", re.compile(r'^play state: 4$'), sc_playing),
        ("pause", re.compile(r'^pause state: 3$'), sc_paused),
        ("stop", re.compile(r'^pause state: 4$'), sc_stopped),
        ("input source", re.compile(r'^new input: file:///(.*?)$'), sc_playing),
    ]


    class QuerierThread(Thread):
        def __init__(self, t):
            self.t = t
            self.data_lock = Lock()
            self.query_queue = []
            self.ready_to_query = False
            self.running = True
            super().__init__(daemon=True)

        def run(self):
            print('Query thread started.')
            sys.stdout.flush()
            while self.running:
                self.lock()
                if self.ready_to_query and len(self.query_queue) > 0:
                    self.ready_to_query = False
                    data = self.query_queue[0]
                    self.send(data[0])
                    print('Sent query: {0}'.format(data[0]))
                    sys.stdout.flush()
                self.unlock()
                time.sleep(0.25)

        def send(self, d):
            self.t.write((d + '\n').encode('ascii'))

        def lock(self):
            self.data_lock.acquire()

        def unlock(self):
            self.data_lock.release()

    class TimeAdvancerThread(Thread):
        def __init__(self, p):
            self.player = p
            super().__init__(daemon=True)

        def run(self):
            try:
                print('Timer thread started.')
                sys.stdout.flush()
                while True:
                    time.sleep(1)
                    self.player.inc_curr_time_if_playing()
                    print(self.player.curr_time)
                    sys.stdout.flush()
            except Exception as e:
                print('Ex:' + e)
                sys.stdout.flush()

    qthread = QuerierThread(t)
    qthread.start()
    tthread = TimeAdvancerThread(player)
    tthread.start()

    query_return_line_re = re.compile(r'^([a-zA-Z_-]+): returned ([0-9]+).*$')
    def query_return_line(line):
        nonlocal query_return_line_re
        nonlocal qthread
        m = query_return_line_re.match(line)
        if m is not None:
            query_name = m.group(1)
            qthread.lock()
            if len(qthread.query_queue) > 0:
                if qthread.query_queue[0][0] == query_name:
                    print('QRL removing {0}'.format(query_name))
                    qthread.query_queue.pop(0)
                    qthread.ready_to_query = True
            qthread.unlock()
            return True
        return False

    def queue_query(query_str, callback):
        nonlocal qthread
        qthread.lock()
        if len(qthread.query_queue) == 0:
            qthread.ready_to_query = True
        qthread.query_queue.append((query_str, callback))
        qthread.unlock()

    def query_response(line):
        nonlocal qthread
        qthread.lock()
        print('Got query response {0}'.format(line))
        sys.stdout.flush()
        if len(qthread.query_queue) == 0:
            qthread.unlock()
            raise IndexError
        else:
            d = qthread.query_queue.pop(0)
            qthread.ready_to_query = True
            d[1](line)
        qthread.unlock()

    def resp_is_playing(line):
        nonlocal player
        if line == '0':
            player.playstate = PlayerState.end
        else:
            player.playstate = PlayerState.play

    def resp_title(line):
        nonlocal player
        player.video_title = line
        print('Set title: {0}'.format(line))
        sys.stdout.flush()

    def resp_get_time(line):
        nonlocal player
        player.curr_time = int(line)
        print('Set current time: {0}'.format(line))
        sys.stdout.flush()

    def resp_get_length(line):
        nonlocal player
        player.total_time = int(line)
        print('Set total time: {0}'.format(line))
        sys.stdout.flush()


    queue_query('is_playing', resp_is_playing)
    queue_query('title', resp_title)
    queue_query('get_time', resp_title)
    queue_query('get_length', resp_title)

    buf = b''
    while True:
        try:
            sys.stdout.flush()
            data = t.read_until(b'\n', 60)
            buf += data
            if buf[-1] != 10:
                sys.stdout.flush()
                continue
        except ConnectionResetError:
            print('Remote connection reset - VLC may have been shut down.')
            sys.stdout.flush()
            sys.exit(0)
        except EOFError:
            print('Remote connection closed - EOF reached.')
            sys.stdout.flush()
            sys.exit(0)

        line = buf.decode('ascii').strip()
        if line != '':
            m = status_change_line.match(line)
            if m is not None:
                matched = False
                for name, check, func in status_changes:
                    mc = check.match(m.group(1))
                    if mc is not None:
                        matched = True
                        func(mc)
                        break
                if not matched:
                    print('Unmatched status change: {0}'.format(m.group(1)))
                    sys.stdout.flush()
            elif query_return_line(line):
                pass
            else:
                try:
                    query_response(line)
                except IndexError:
                    print('Unmatched line: "{0}"'.format(line))
                    sys.stdout.flush()
                except QueryValueError as q:
                    print('Invalid value for query "{0}": {1}'.format(q.query, q.value))
                    sys.stdout.flush()
        buf = b''


if __name__ == "__main__":
    main()
