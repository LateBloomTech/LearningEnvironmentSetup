# pyright: strict
import timeit   #小さい Python コードをの時間を計測

def test(n): 
    return sum(range(n)) 


n = 10000
loop = 1000


result = timeit.timeit('test(n)',globals=globals(),number=loop) 

print(result/loop)
# 参考サイト　https://note.nkmk.me/python-timeit-measure/
# i512450h 6.260639999527485e-05
#計測シングルコアの模様