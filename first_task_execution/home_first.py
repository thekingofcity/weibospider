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
            for line in open(r'uid.txt', 'r', encoding='utf8'):
                line = line[:len(line) - 1]  # remove the final \n
                # print(line)
                execute_home_task(line)
