import sys

sys.path.append('.')
sys.path.append('..')

from tasks import execute_login_task
from tasks.login import push_account_to_login_pool, check_heartbeat

if __name__ == '__main__':
    check_heartbeat()
    execute_login_task()
