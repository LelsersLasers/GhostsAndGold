import threading
import multiprocessing
import time


def calcs(n: int) -> None:
    for i in range(n):
        x = i ** 4


def basic(n: int) -> float:
    start = time.time()
    calcs(n)
    return time.time() - start


def threads(n: int, s: int) -> float:
    start = time.time()

    ts: list[threading.Thread] = []

    for _ in range(s):
        t = threading.Thread(target=calcs, args=(n // s,))
        ts.append(t)
        t.start()

    for t in ts:
        t.join()

    return time.time() - start

def process(n: int, s: int) -> float:
    start = time.time()

    ps: list[multiprocessing.Process] = []

    for _ in range(s):
        p = multiprocessing.Process(target=calcs, args=(n // s,))
        ps.append(p)
        p.start()

    for p in ps:
        p.join()

    return time.time() - start


def main():
    n = 11 ** 7 + 1
    s = 4
    print(n, n // 2)
    basic_time = basic(n)
    threads_time = threads(n, s)
    process_time = process(n, s)

    print("BASIC TIME:", basic_time)
    print("THREADS TIME:", threads_time)
    print("PROCESS TIME:", process_time)



if __name__ == "__main__":
    main()