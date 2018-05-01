import sys

sys.path.append('.')
sys.path.append('..')

from tasks.user import (execute_user_task, execute_extend_user_task)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        execute_user_task()
    else:
        execute_extend_user_task()
