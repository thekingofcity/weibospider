import sys

from res import uid2name__

sys.path.append('.')
sys.path.append('..')

from tasks.user import execute_followers_fans_task

if __name__ == '__main__':
    if len(sys.argv) == 3:
        if sys.argv[1].isdigit() and sys.argv[2].isdigit():
            execute_followers_fans_task(int(sys.argv[1]), int(sys.argv[2]))
        else:
            print("Please input standard uid.")
    elif len(sys.argv) == 1:
        for uid in uid2name__:
            execute_followers_fans_task(uid, uid2name__[uid][1])
    elif len(sys.argv) < 3:
        print("Please specific an uid and a verify_type.")
    else:
        print("Only one uid and one verify_type at a time.")
