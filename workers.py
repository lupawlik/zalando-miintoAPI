from threading import Thread
import ctypes


thread_list = []  # list of running thread

# return true if worker exist in list
def __check_if_thread_is_running(name):
    for i in range(len(thread_list)):
        if thread_list[i].name == name:
            print("Worker nie zostal uruchomionym juz taki istnieje pod id:", thread_list[i].ident)
            return True
    return False

# return list of names of running workers
def get_list_of_threads():
    thread_name_list = []
    if len(thread_list) == 0:  # when 0 workers is running
        thread_name_list.append('Brak')
        return thread_name_list
    for i in range(len(thread_list)):
        thread_name_list.append(thread_list[i].name)
    return thread_name_list

# create new thread/worker
# function = name of function that's runs on threading
# args = all function parameters
def run_new_thread(name, function, *args):
    if __check_if_thread_is_running(name):
        return "Worker juz urochomiony"
    # run new worker and add to the list
    thread = Thread(target=function, args=(args))
    thread.name = name
    thread.daemon = True
    thread.start()
    thread_list.append(thread)
    return "Uruchomiono workera: "+thread.name

# remove worker from list
def del_from_list(name):
    for i in range(len(thread_list)):
        if thread_list[i].name == name:  # check if given worker exist
            del thread_list[i]
            print(f"Usunieto z listy workerow {name}")

# search thread by name, if exist kill it
def kill_thread(name):
    for i in range(len(thread_list)):
        if thread_list[i].name == name:
            thread_to_kill = thread_list[i]
    try:
        thread_id = thread_to_kill.ident  # get thread id
    except:
        print("Nie ma workera o tej nazwie")  # run when not thread with given name in thread_lis
        return "Nie ma workera o tej nazwie"
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit)) # kill worker process

    if res > 1:  # if failure
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
        print("Zatrzymanie workera nie powiodlo sie")
        return "Zatrzymanie workera nie powiodlo sie"
    else: 
        print("Zatrzymano workera", thread_to_kill.name)
        del_from_list(name)