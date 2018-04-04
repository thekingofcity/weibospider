import sys

sys.path.append('.')
sys.path.append('..')

from tasks import crawl_follower_fans

if __name__ == '__main__':
    if len(sys.argv) == 2:
        if sys.argv[1].isdigit():
            crawl_follower_fans(int(sys.argv[1]))
        else:
            print("Please input standard uid.")
    elif len(sys.argv) == 1:
        print("Please specific an uid.")
    else:
        print("Only one uid at a time.")
