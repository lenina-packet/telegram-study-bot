import sys
sys.setrecursionlimit(10**5)

def F(start, end, stop):
    a = [0] * 1000
    a[start] = 1
    for i in range (start, end - 1, -1):
        for k in stop:
            a[k] = 0
        a[i - 1] += a[i]
        a[i // 2] += a[i]
    return a[end]
print(F(30, 1, []))