import sys

sys.path.append('.')
sys.path.append('..')

from tasks import execute_praise_task


if __name__ == '__main__':
    if len(sys.argv) == 1:
        execute_praise_task()
    elif len(sys.argv) == 2:
        if sys.argv[1].isdigit():
            execute_praise_task(sys.argv[1])
