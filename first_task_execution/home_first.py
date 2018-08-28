import sys

from res import resources

sys.path.append('.')
sys.path.append('..')

from tasks import execute_home_task

if __name__ == '__main__':
    if len(sys.argv) == 1:
        execute_home_task()
    elif len(sys.argv) == 2:
        if sys.argv[1].isdigit():
            execute_home_task(sys.argv[1])
        else:
            res = resources().fetchAll()
            for uid in res:
                execute_home_task(uid)
