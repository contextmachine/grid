import threading as th
import time
from queue import Queue


class StateManager:
    """

    @procs - массив сохраняющих функций передается непосредственно в state-manager loop.
    Благодаря своей неблокирующей природе а также правильном испльзовании флага состояния,
    может быть корректно обработан массив функций любой длины и продолжительности выполнения.

    """

    def __init__(self, procs, sleep_time=10):
        super().__init__()
        self.procs = procs
        self.update_flag = False
        self.stop_flag = False
        self.sleep_time = sleep_time
        self.paused = set()
        self.manual_runs = set()
        def loop():

            while True:

                if self.stop_flag:
                    print("stopping")
                    break

                elif self.update_flag:
                    self.update_flag = False

                    for i, proc in enumerate(self.procs):
                        if i not in self.paused:
                            proc()
                            if i in self.manual_runs:
                                self.manual_runs.remove(i)




                else:
                    for i in list(self.manual_runs):
                        print(f"running {i} {self.procs[i].__name__} manually...")
                        self.procs[i]()
                        self.manual_runs.remove(i)
                    time.sleep(self.sleep_time)
                    continue

        self.thread = th.Thread(target=loop)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        a, b, c = args
        if (a, b, c) == (None, None, None):
            pass
        else:
            self.stop_flag = True

    def pause(self, i):
        self.paused.add(i)

    def resume(self, i):
        self.manual_runs.add(i)
        self.paused.remove(i)

    def stop(self):
        self.stop_flag = True

    def update(self):

        self.update_flag = True
