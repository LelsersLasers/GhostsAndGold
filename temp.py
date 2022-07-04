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