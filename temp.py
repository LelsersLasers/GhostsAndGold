# from typing import Union

# class A:
#     def __init__(self, x: int):
#         self.x = x
#     def __str__(self):
#         return "%i" % self.x
# class B(A):
#     def __init__(self):
#         super().__init__(1)
# class C(A):
#     def __init__(self):
#         super().__init__(2)
    

# b_lst = [B(), B()]
# c_lst = [C(), C()]
# combined: list[B|C] = b_lst + c_lst

# print("b_list")
# for b in b_lst:
#     print(b, end=" ")
# print("\nc_list")
# for c in c_lst:
#     print(c, end=" ")
# print("\ncombined")
# for a in combined:
#     print(a, end=" ")


a_lst = list("0123456789")

for a in a_lst:
    print(a, end=" ")
    if int(a) % 4 == 0 or int(a) % 3 == 0:
        print("x", end=" ")
        a_lst.remove(a)
print("")
print(a_lst)

# a_lst = list("0123456789")

# for i in range(len(a_lst)):
#     print(a_lst[i], end=" ")
#     if int(a_lst[i]) % 4 == 0:
#         a_lst.remove(a_lst[i])

a_lst = list("0123456789")

for i in range(len(a_lst) - 1, -1, -1):
    print(a_lst[i], end=" ")
    if int(a_lst[i]) % 4 == 0 or int(a_lst[i]) % 3 == 0:
        del a_lst[i]
print("")
print(a_lst)
        

print("")