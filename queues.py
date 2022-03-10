import sqlite3
import time

# class used to make query to database, takes name of database and delay
class DbQueue(object):
    def __init__(self, db_name, delay: int):
        self.queue_list = []
        self.delay = delay
        self.name = db_name
        self.conn = sqlite3.connect(str(self.name), check_same_thread=False)
        self.c = self.conn.cursor()

    # runs query to db. Return true if success
    def __execute_query(self, query):
        try:
            self.c.execute(query)
            self.conn.commit()
            print(f"[{self.name} - queue] SUCCESS - {query}")
            return True
        except Exception as e:
            print(f"[{self.name} - queue] FAILED - {e}")
            return False

    # pop element form queue list
    def _remove_from_q(self, element_position):
        self.queue_list.pop(element_position)
        return True

    # add element to queue list
    def add(self, argument: str):
        self.queue_list.append(argument)
        return True

    def get_list(self):
        return self.queue_list

    def get_number_of_task(self):
        return len(self.queue_list)

    def start(self):
        while True:
            if self.queue_list:
                for i, v in enumerate(self.queue_list):
                    self.__execute_query(v)
                    self._remove_from_q(i)
            else:
                time.sleep(self.delay)

class ZalandoQueue(object):
    def __init__(self, name: str, delay: int):
        self.name = name
        self.task_list = []

    def add(self, function_name: str, type: str):
        self.task_list.append((function_name, type))

    def start(self):
        while True:
            pass
