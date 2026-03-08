# test_parallel.py
from concurrent.futures import ProcessPoolExecutor
import numpy as np, os, time

def heavy(i):
    os.environ["OMP_NUM_THREADS"]      = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"]      = "1"
    x = np.random.rand(500, 500)
    for _ in range(50):
        x = x @ x.T / 500
    return i

if __name__ == "__main__":
    n = os.cpu_count()
    print(f"CPU 核心數: {n}")

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(heavy, range(n)))
    print(f"平行耗時: {time.time()-t0:.2f}s  結果: {results}")

    t0 = time.time()
    for i in range(n):
        heavy(i)
    print(f"序列耗時: {time.time()-t0:.2f}s")
