
a_lst = list("01234567890")
for i in range(len(a_lst) - 1, -1, -1):
    print(a_lst[i], end=" ")
    del a_lst[i]
print(a_lst)

a_lst = list("01234567890")
for i in range(len(a_lst)):
    print(a_lst[i], end=" ")
    del a_lst[i]